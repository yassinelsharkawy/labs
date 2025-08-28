# Lab 7 — Password Reset Token Reuse After Password Change

## 1. Objective

Demonstrate how failing to invalidate outstanding password reset tokens upon a user password change allows previously generated tokens to hijack account credentials.

## 2. Scenario

A user requests a password reset token. Before the token is redeemed, the user signs into their active session and updates their password. Because the password change handler updates the password hash without revoking pending reset tokens, an attacker with access to the earlier reset token can reuse it to overwrite the user's password.

**Trust boundary:** The application assumed that reset tokens are naturally self-limiting without explicitly tracking account-wide invalidation events.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target account | `alice` / `alice123` |
| Token state | Unused token generated in `password_reset_tokens` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The password change handler updates the user's password hash in `users` but leaves active records in `password_reset_tokens` with `used = 0`:

```sql
UPDATE users SET password_hash = ? WHERE id = ?
```

When the reset endpoint checks token validity:

```sql
SELECT * FROM password_reset_tokens WHERE token = ? AND used = 0
```

The prior token is still considered valid and permits setting a new password.

## 5. Reproduction

1. Request a password reset token for `alice`:

```bash
curl -X POST http://localhost:5000/lab/auth/auth-02/request-reset \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}'
```

2. Alice logs in and changes her password normally:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"

curl -b cookies.txt -X POST http://localhost:5000/lab/auth/auth-02/change-password \
  -H "Content-Type: application/json" \
  -d '{"current_password": "alice123", "new_password": "newpassword456"}'
```

3. Use the original reset token to reset Alice's password:

```bash
curl -X POST http://localhost:5000/lab/auth/auth-02/reset \
  -H "Content-Type: application/json" \
  -d '{"token": "<TOKEN>", "new_password": "hijackedpassword"}'
```

## 6. Evidence

The reset request succeeds with HTTP 200:

```json
{
  "message": "Password reset successful"
}
```

The user is now locked out of their legitimate credentials.

## 7. Root Cause

**File:** `app/routes/auth_labs.py`  
**Function:** `lab07_change_password()`

The handler does not invalidate pending reset tokens upon password update in vulnerable mode.

## 8. Impact

An attacker who intercepts an old email link or recovers an exposed reset token can re-compromise an account even after the user has changed their credentials.

## 9. Remediation

Invalidate all outstanding reset tokens whenever a password modification occurs:

```python
db.execute(
    "UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0",
    (user['id'],)
)
```

## 10. Regression Validation

**Test:** `tests/test_lab_07.py`

- **Vulnerable mode:** Reset token usable after password change → HTTP 200.
- **Patched mode:** Reset token rejected after password change → HTTP 400.
- **Legitimate flow:** Single reset token consumed prior to any password change → HTTP 200.

## 11. Research Discussion

1. What state synchronization events should trigger token invalidation across account lifecycle management?
2. How can timestamp-based token validation (e.g., tokens valid only if created after `password_last_changed`) eliminate database cleanup overhead?
3. What security telemetry should alert when an invalidated or expired reset token is submitted?
