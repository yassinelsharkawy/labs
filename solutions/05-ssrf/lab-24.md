# Lab 24 — SSRF via Redirect Bypass of URL Allowlist

## 1. Objective

Demonstrate how following HTTP redirects blindly allows attackers to bypass pre-flight URL validation checks and access restricted internal resources.

## 2. Scenario

A social collaboration platform provides a link preview generator (`/fetch-preview`) that fetches remote URLs to extract OpenGraph metadata and page titles. The application implements an allowlist/filter that inspects the initial user-provided URL against private IP addresses and loopback hostnames. However, when issuing the outbound request, the HTTP client has redirect following enabled (`allow_redirects=True`). An attacker can supply a public URL that issues an HTTP 302 redirect targeting an internal service, bypassing the initial check.

**Trust boundary:** The application assumed that validating the initial request URL ensures that all subsequent redirection hops remain within policy.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/ssrf/ssrf-04/fetch-preview` |
| Redirector helper | `/lab/ssrf/ssrf-04/redirector?target=...` |
| Internal service target | `http://127.0.0.1:5001/internal/health` |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The application checks only the incoming URL string:

```python
if not _naive_hostname_check(url):
    return jsonify({'error': 'URL blocked'}), 403
```

If the initial URL is public (e.g. `http://service.partner.local/preview` or an external redirect service), the check passes. The server then executes:

```python
resp = http_requests.get(url, timeout=5, allow_redirects=True)
```

The underlying HTTP client follows HTTP 301/302 redirects automatically without re-invoking the validation routine. The target server responds with a `Location: http://127.0.0.1:5001/internal/health` header, prompting the client to connect directly to the loopback service.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Construct a redirect target pointing to the local redirector helper:

```bash
REDIRECT_URL="http://service.partner.local/preview"
```

3. Submit the initial request to the link preview endpoint:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/ssrf/ssrf-04/fetch-preview \
  -H "Content-Type: application/json" \
  -d '{"url": "http://service.partner.local/preview"}'
```

4. Verify that the response returns data retrieved from the redirect destination.

## 6. Evidence

The response reveals HTTP 200 containing data retrieved from the secondary redirection hop:

```json
{
  "body_preview": "simulated internal response",
  "status_code": 200
}
```

The application followed the redirect from an allowed initial URL into an internal service.

## 7. Root Cause

**File:** `app/routes/ssrf.py`  
**Function:** `lab24_fetch_preview()`

In vulnerable mode, the endpoint enables automatic redirect following on the HTTP client:

```python
if patched:
    # Follow redirects manually, validating at each step
    current_url = url
    for _ in range(10):
        safe, reason = _is_url_safe(current_url)
        if not safe:
            return jsonify({'error': f'URL blocked at redirect: {reason}'}), 403
        resp = http_requests.get(current_url, timeout=5, allow_redirects=False)
        if resp.is_redirect:
            current_url = resp.headers.get('Location', '')
            continue
        return jsonify({'status_code': resp.status_code, 'body_preview': resp.text[:2048]})
else:
    if not _naive_hostname_check(url):
        return jsonify({'error': 'URL blocked'}), 403
    resp = http_requests.get(url, timeout=5, allow_redirects=True)
```

## 8. Impact

An attacker can bypass domain allowlists, network boundary firewalls, and URL validation filters by laundering requests through intermediate public redirection endpoints.

## 9. Remediation

Disable automatic redirect following (`allow_redirects=False`) and manually validate every hop against network safety policies before making subsequent requests:

```python
current_url = url
for _ in range(10):
    safe, reason = _is_url_safe(current_url)
    if not safe:
        return jsonify({'error': f'URL blocked at redirect: {reason}'}), 403
    resp = http_requests.get(current_url, timeout=5, allow_redirects=False)
    if resp.is_redirect:
        current_url = resp.headers.get('Location', '')
        if not current_url:
            break
        continue
    return jsonify({'status_code': resp.status_code, 'body_preview': resp.text[:2048]})
```

## 10. Regression Validation

**Test:** `tests/test_lab_24.py`

- **Vulnerable mode:** Automatic redirect following executes successfully.
- **Patched mode:** Redirection hop targeting loopback (`127.0.0.1`) returns HTTP 403 (`URL blocked at redirect`).
- **Legitimate flow:** Empty URL submission returns HTTP 400.

## 11. Research Discussion

1. Why do default HTTP client configurations (in Python `requests`, Go `net/http`, cURL) follow redirects by default?
2. How does DNS rebinding introduce similar bypass risks even when initial DNS resolution appears safe?
3. What is the difference between preventing redirect following entirely versus validating intermediate hops?
