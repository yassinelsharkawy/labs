# Lab 9 — OTP Replay and Non-Consumption

## 1. Objective

Demonstrate how failing to mark one-time passcode (OTP) verification tokens as consumed upon validation permits code replay attacks.

## 2. Scenario

An application sends temporary numeric OTP codes for sensitive actions or secondary authentication. When a user submits the OTP code, the backend verifies that the code matches a token record where `used = 0`. However, the handler omits the update statement that sets `used = 1`. Consequently, the same OTP can be submitted repeatedly.

**Trust boundary:** The application assumed verification logic inherently consumes the underlying token.

## 3. Preconditions

| Item | Value |
|------|-------|
| Authenticated user | `heidi` / `heidi123` |
| Token state | Fresh OTP generated in `verification_tokens` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The endpoint validates OTP presence:

```sql
SELECT * FROM verification_tokens WHERE user_id = ? AND token = ? AND used = 0
```

Because the record is never updated with `SET used = 1`, subsequent verification attempts continue to match the existing row.

## 5. Reproduction

1. Log in as `heidi`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=heidi&password=heidi123"
```

2. Request an OTP code:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/auth/auth-04/send-otp
```

3. Submit the received OTP code for verification:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/auth/auth-04/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"otp_code": "<OTP>"}'
```

4. Resubmit the identical OTP code:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/auth/auth-04/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"otp_code": "<OTP>"}'
```

## 6. Evidence

Both requests return HTTP 200 indicating successful verification:

```json
{
  "message": "OTP verified successfully",
  "verified": true
}
```

The database query confirms `used` remains `0`.

## 7. Root Cause

**File:** `app/routes/auth_labs.py`  
**Function:** `lab09_verify_otp()`

In unpatched mode, the application checks the token but never executes the consumption update:

```python
if patched:
    db.execute("UPDATE verification_tokens SET used = 1 WHERE id = ?", (row['id'],))
    db.commit()
```

## 8. Impact

An attacker who intercepts or observes an OTP code (e.g. via shoulder-surfing, insecure logging, or network interception) can reuse the token within its validity window.

## 9. Remediation

Mark the verification token as consumed atomically upon verification:

```python
db.execute("UPDATE verification_tokens SET used = 1 WHERE id = ?", (row['id'],))
db.commit()
```

## 10. Regression Validation

**Test:** `tests/test_lab_09.py`

- **Vulnerable mode:** Replayed OTP succeeds on second submission → HTTP 200.
- **Patched mode:** Replayed OTP is rejected on second submission → HTTP 400.
- **Legitimate flow:** Single OTP submission succeeds on first use → HTTP 200.

## 11. Research Discussion

1. Why are single-use guarantees critical for time-based and challenge-response authentication tokens?
2. What database race conditions can emerge if token consumption is not executed atomically?
3. What rate-limiting and brute-force protections should complement OTP token consumption?
