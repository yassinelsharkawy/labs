# Lab 8 — Session Persistence After Password Change

## 1. Objective

Demonstrate how failing to revoke active sessions upon a credential change allows unauthorized or compromised concurrent sessions to persist indefinitely.

## 2. Scenario

A user suspects unauthorized activity on their account and initiates a password change to secure their profile. However, while the database records the updated password hash, the session storage mechanism fails to revoke or invalidate other existing session tokens issued prior to the password modification.

**Trust boundary:** The application assumed that changing credentials naturally invalidates all active sessions.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target account | `alice` / `alice123` |
| Session state | Multiple active session tokens in `sessions` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The password change handler updates `password_hash` in `users`:

```sql
UPDATE users SET password_hash = ? WHERE id = ?
```

However, active records in `sessions` remain with `revoked = 0`. Any device or client possessing a previously issued token can continue invoking authenticated API routes without re-authenticating.

## 5. Reproduction

1. Establish Session 1 and Session 2 for `alice`:

```bash
curl -X POST http://localhost:5000/lab/auth/auth-03/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "alice123"}'
```

2. Using Session 1, change Alice's password:

```bash
curl -X POST http://localhost:5000/lab/auth/auth-03/change-password \
  -H "Authorization: Bearer <TOKEN_1>" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "alice123", "new_password": "newalicepassword"}'
```

3. Attempt to access Alice's profile using Session 2:

```bash
curl http://localhost:5000/lab/auth/auth-03/profile \
  -H "Authorization: Bearer <TOKEN_2>"
```

## 6. Evidence

Session 2 continues to retrieve user profile data with HTTP 200:

```json
{
  "email": "alice@corp.local",
  "role": "user",
  "user_id": 2,
  "username": "alice"
}
```

The session remained active despite the password change.

## 7. Root Cause

**File:** `app/routes/auth_labs.py`  
**Function:** `lab08_change_password()`

In vulnerable mode, the endpoint does not mark other sessions as revoked:

```python
if patched:
    db.execute(
        "UPDATE sessions SET revoked = 1 WHERE user_id = ? AND session_token != ?",
        (user['id'], token),
    )
```

## 8. Impact

An attacker with an existing stolen session or session cookie retains persistent access to the victim account even after the victim changes their password.

## 9. Remediation

Explicitly revoke all other active sessions for the user upon password modification:

```python
db.execute(
    "UPDATE sessions SET revoked = 1 WHERE user_id = ? AND session_token != ?",
    (user['id'], token)
)
```

## 10. Regression Validation

**Test:** `tests/test_lab_08.py`

- **Vulnerable mode:** Session 2 remains valid after password change → HTTP 200.
- **Patched mode:** Session 2 is revoked → HTTP 401 Unauthorized.
- **Legitimate flow:** Current session (Session 1) remains valid → HTTP 200.

## 11. Research Discussion

1. Why is global session invalidation a mandatory security requirement for password reset and change workflows?
2. How do stateless JWT architectures address global session revocation compared to database-backed session stores?
3. What UX considerations exist when deciding whether to revoke the current active session alongside remote sessions?
