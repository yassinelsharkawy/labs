# Lab 21 — Image Importer SSRF to Internal Metadata

## 1. Objective

Demonstrate how an unvalidated external image import feature allows attackers to trigger Server-Side Request Forgery (SSRF) targeting internal service endpoints.

## 2. Scenario

A web application allows users to import avatar or profile banner images by specifying a remote URL (`/import-image`). The server fetches the provided URL using an HTTP client, reads the response body, and saves the binary or text content. However, the application performs no validation on the destination host, scheme, or IP address, allowing requests to reach internal services and metadata servers.

**Trust boundary:** The application assumed that URL inputs would refer only to public third-party image hosts.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/ssrf/ssrf-01/import-image` |
| Mock internal service | `http://127.0.0.1:5001/internal/health` (or `http://mock-internal:5001`) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The backend extracts the `url` parameter from the JSON request body and immediately invokes `http_requests.get(url, timeout=5)`:

```python
resp = http_requests.get(url, timeout=5)
body = resp.text[:4096]
db.execute("INSERT INTO imported_images (user_id, source_url, stored_data) VALUES (?, ?, ?)", ...)
```

Because the HTTP request originates from the server inside the network perimeter, it can reach loopback (`127.0.0.1`), link-local metadata endpoints (`169.254.169.254`), and internal Docker container hostnames (`mock-internal:5001`).

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit an import request targeting an internal service endpoint:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/ssrf/ssrf-01/import-image \
  -H "Content-Type: application/json" \
  -d '{"url": "http://127.0.0.1:5001/internal/health"}'
```

3. Parse the returned JSON response.

## 6. Evidence

The endpoint returns HTTP 200 containing data retrieved from the internal service:

```json
{
  "body_preview": "{\"service\": \"internal-api\", \"status\": \"healthy\"}",
  "content_type": "application/json",
  "source_url": "http://127.0.0.1:5001/internal/health",
  "status": "imported"
}
```

The application successfully retrieved and surfaced internal network information.

## 7. Root Cause

**File:** `app/routes/ssrf.py`  
**Function:** `lab21_import_image()`

In vulnerable mode, the server omits IP address validation and destination filtering:

```python
if patched:
    safe, reason = _is_url_safe(url)
    if not safe:
        return jsonify({'error': f'URL blocked: {reason}'}), 403
```

## 8. Impact

Attackers can probe internal network topologies, read cloud instance metadata (tokens, IAM credentials), access unprotected internal microservices, and bypass network perimeter firewalls.

## 9. Remediation

Validate schemes (`http`/`https`), resolve DNS hostnames before issuing HTTP requests, and verify that resolved IP addresses do not belong to private, loopback, or link-local ranges:

```python
def _is_url_safe(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, 'Invalid scheme'
    
    # Resolve hostname
    results = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
    for family, type_, proto, canonname, sockaddr in results:
        ip = sockaddr[0]
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
            return False, 'Target IP is within a restricted network range'
    return True, 'ok'
```

## 10. Regression Validation

**Test:** `tests/test_lab_21.py`

- **Vulnerable mode:** Internal target returns HTTP 200 with `body_preview` containing `internal-api`.
- **Patched mode:** Internal target returns HTTP 403 (`URL blocked: Hostname resolves to private IP`).
- **Legitimate flow:** Empty URL correctly rejected with HTTP 400.

## 11. Research Discussion

1. Why is DNS resolution validation required even if hostnames are checked against static domain blocklists?
2. What are the security risks associated with cloud instance metadata services (IMDSv1 vs. IMDSv2)?
3. How can network egress firewalls and network policies (e.g. Calico, AWS Security Groups) provide defense-in-depth against SSRF?
