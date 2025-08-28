# Lab 10 — OAuth State Parameter Fixation

## 1. Objective

Demonstrate how failing to bind the OAuth `state` parameter to the originating user session allows state fixation attacks leading to account linking manipulation.

## 2. Scenario

An application supports third-party OAuth authentication. When initiating authorization, the application generates a random `state` token and stores it in the database. However, the generated `state` token is stored without associating it with the initiator's session or user identity. When an authorization callback is processed, the application validates only that the `state` token exists in the database.

**Trust boundary:** The application assumed that validating state token existence is sufficient to prevent CSRF and fixation.

## 3. Preconditions

| Item | Value |
|------|-------|
| Initiating user | `alice` (generates state token) |
| Consuming user | `eve` (consumes callback with Alice's state) |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

During authorization initiation:

```sql
INSERT INTO oauth_states (state_token, provider) VALUES (?, ?)
```

The user identity is omitted. During the callback:

```sql
SELECT * FROM oauth_states WHERE state_token = ? AND used = 0
```

The query validates that the token exists, but does not verify that the session completing the callback matches the session that initiated the request.

## 5. Reproduction

1. Alice initiates an OAuth flow and obtains a state token:

```bash
curl -c alice_cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"

curl -b alice_cookies.txt -X POST http://localhost:5000/lab/auth/auth-05/oauth/authorize
```

2. Eve (attacker) consumes the callback using Alice's state token:

```bash
curl -c eve_cookies.txt -X POST http://localhost:5000/login \
  -d "username=eve&password=eve123"

curl -b eve_cookies.txt "http://localhost:5000/lab/auth/auth-05/oauth/callback?state=<ALICE_STATE>&code=testcode123"
```

3. Observe that Eve's callback request succeeds without error.

## 6. Evidence

The callback endpoint returns HTTP 200 indicating successful state validation:

```json
{
  "message": "OAuth authorization completed successfully",
  "status": "connected"
}
```

The state was accepted across different user sessions.

## 7. Root Cause

**File:** `app/routes/auth_labs.py`  
**Functions:** `lab10_oauth_authorize()` and `lab10_oauth_callback()`

The authorization handler stores the state token unbound to `session['user_id']`, and the callback handler does not verify matching session ownership:

```python
if patched:
    if 'user_id' not in session or row['user_id'] != session['user_id']:
        return jsonify({'error': 'State token does not belong to current session'}), 403
```

## 8. Impact

An attacker can trick a victim into completing an authorization request using the attacker's pre-generated state token, binding the victim's social identity to the attacker's account, or vice versa.

## 9. Remediation

Bind the OAuth `state` parameter to the initiating user's session identifier or store it in an encrypted session cookie:

```python
# Authorization initiation:
db.execute(
    "INSERT INTO oauth_states (state_token, user_id, provider) VALUES (?, ?, ?)",
    (state, session['user_id'], 'example-provider')
)

# Callback validation:
if row['user_id'] != session.get('user_id'):
    return jsonify({'error': 'State token does not belong to current session'}), 403
```

## 10. Regression Validation

**Test:** `tests/test_lab_10.py`

- **Vulnerable mode:** Eve completes callback using Alice's state token → HTTP 200.
- **Patched mode:** Eve completes callback using Alice's state token → HTTP 403 Forbidden.
- **Legitimate flow:** Alice completes callback using her own state token → HTTP 200.

## 11. Research Discussion

1. How does the OAuth 2.0 `state` parameter defend against Cross-Site Request Forgery (CSRF)?
2. What are the advantages of storing OAuth state values in client-side signed session cookies versus database tables?
3. How does PKCE (Proof Key for Code Exchange) provide defense-in-depth alongside the `state` parameter?
