# Lab 23 — Report Generator SSRF via Document URL

## 1. Objective

Demonstrate how automated document and PDF/HTML report generation features that fetch remote templates or assets can be abused for Server-Side Request Forgery.

## 2. Scenario

An analytics and reporting dashboard allows managers to generate customized executive summary reports by providing a `source_url` pointing to an external HTML or markdown template. The server fetches the document from the specified URL and incorporates the retrieved content directly into the generated report payload. The application does not restrict target schemes or destination host addresses.

**Trust boundary:** The application assumed that report templates would only be fetched from trusted external public CDN endpoints.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/ssrf/ssrf-03/generate-report` |
| Mock internal service | `http://127.0.0.1:5001/internal/health` (or `http://mock-internal:5001`) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The endpoint accepts `source_url` in the JSON request body and fetches the target:

```python
resp = http_requests.get(source_url, timeout=5)
report_content = resp.text[:4096]
return jsonify({
    'status': 'report_generated',
    'source': source_url,
    'report_html': report_content,
})
```

Because the server performs no destination validation, an attacker can specify internal service endpoints, causing the server to fetch and reflect sensitive internal responses in the generated report output.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Request report generation targeting an internal service URL:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/ssrf/ssrf-03/generate-report \
  -H "Content-Type: application/json" \
  -d '{"source_url": "http://127.0.0.1:5001/internal/health"}'
```

3. Inspect the returned report content.

## 6. Evidence

The report generation response contains the content fetched from the internal endpoint:

```json
{
  "report_html": "{\"service\": \"internal-api\", \"status\": \"healthy\"}",
  "source": "http://127.0.0.1:5001/internal/health",
  "status": "report_generated"
}
```

The server incorporated internal network information directly into the report.

## 7. Root Cause

**File:** `app/routes/ssrf.py`  
**Function:** `lab23_generate_report()`

In vulnerable mode, the endpoint issues an outbound HTTP request without validating whether the resolved address belongs to a private network:

```python
if patched:
    safe, reason = _is_url_safe(source_url)
    if not safe:
        return jsonify({'error': f'URL blocked: {reason}'}), 403
```

## 8. Impact

An attacker can access internal network services, cloud instance metadata credentials, and internal administrative panels, embedding internal data into exportable reports.

## 9. Remediation

Validate the URL against an explicit domain allowlist or verify that resolved IP addresses do not point to private or loopback ranges:

```python
safe, reason = _is_url_safe(source_url)
if not safe:
    return jsonify({'error': f'URL blocked: {reason}'}), 403
```

For PDF/HTML rendering engines (e.g. wkhtmltopdf, Puppeteer), also disable local file access (`--disable-local-file-access`) and external network requests.

## 10. Regression Validation

**Test:** `tests/test_lab_23.py`

- **Vulnerable mode:** Internal target returns HTTP 200 with `report_html` containing `internal-api`.
- **Patched mode:** Internal target returns HTTP 403 (`URL blocked`).
- **Legitimate flow:** Empty `source_url` submission is rejected with HTTP 400.

## 11. Research Discussion

1. Why are headless browsers and HTML-to-PDF rendering pipelines common high-impact vectors for SSRF?
2. How can attackers pivot from SSRF to local file read (`file:///etc/passwd`) in document rendering services?
3. What network containerization strategies isolate rendering worker nodes from sensitive internal infrastructure?
