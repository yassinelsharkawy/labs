# Lab 19 — Parallel Verification Token Consumption

## 1. Objective

Demonstrate how race conditions during verification token consumption permit multiple rewards or account credits to be minted from a single one-time token.

## 2. Scenario

An application rewards users with a promotional account balance credit of $10.00 upon verifying their account with a one-time verification token. When a user submits the token, the backend checks if the token exists and is unused (`used == 0`). If valid, the system credits the user's wallet and subsequently marks the token record as used (`used = 1`). Because the credit is awarded before the token is marked as consumed, parallel requests can claim the reward multiple times.

**Trust boundary:** The application assumed that side-effect actions (crediting money) could occur prior to marking single-use tokens consumed.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/logic/logic-04/verify` |
| Verification token | `VERIFY-TOKEN-ALICE-001` |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /lab/logic/logic-04/reset`) |

## 4. Vulnerability Mechanism

When verifying a token, the endpoint queries:

```sql
SELECT * FROM verification_tokens WHERE token = ? AND used = 0
```

If a row is found, it updates the user's wallet balance:

```sql
UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?
```

Finally, it marks the token as used:

```sql
UPDATE verification_tokens SET used = 1 WHERE id = ?
```

In high-concurrency scenarios, two requests reading simultaneously both see `used = 0`, both execute the wallet update, crediting the balance multiple times before either updates `used = 1`.

## 5. Reproduction

1. Log in as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Reset the verification token and wallet state:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-04/reset
```

3. Submit concurrent verification requests using the same token:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-04/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "VERIFY-TOKEN-ALICE-001"}' &
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-04/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "VERIFY-TOKEN-ALICE-001"}' &
wait
```

4. Retrieve user wallet balance:

```bash
curl -b cookies.txt http://localhost:5000/lab/logic/logic-04/tokens
```

## 6. Evidence

Both verification requests succeed with HTTP 200:

```json
{
  "credit": 10.0,
  "new_balance": 120.0,
  "status": "verified"
}
```

The wallet balance increased by $20.00 rather than the expected single $10.00 credit.

## 7. Root Cause

**File:** `app/routes/logic.py`  
**Function:** `lab19_verify()`

The handler grants the wallet credit before committing the token status change:

```python
if patched:
    cur = db.execute(
        "UPDATE verification_tokens SET used = 1 WHERE token = ? AND used = 0",
        (token,)
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'error': 'Token invalid or already used'}), 400
    # Only credit wallet after guaranteed atomic token consumption
    db.execute("UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?", (vt['user_id'],))
    db.commit()
else:
    vt = db.execute("SELECT * FROM verification_tokens WHERE token = ? AND used = 0", (token,)).fetchone()
    if not vt:
        return jsonify({'error': 'Token invalid or already used'}), 400
    db.execute("UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?", (vt['user_id'],))
    db.execute("UPDATE verification_tokens SET used = 1 WHERE id = ?", (vt['id'],))
    db.commit()
```

## 8. Impact

Attackers can duplicate sign-up bonuses, referral rewards, or account gift balances, causing financial losses.

## 9. Remediation

Consume the token atomically as the primary gating operation before executing any business side-effects:

```python
cur = db.execute(
    "UPDATE verification_tokens SET used = 1 WHERE token = ? AND used = 0",
    (token,)
)
db.commit()
if cur.rowcount == 0:
    return jsonify({'error': 'Token invalid or already used'}), 400

db.execute(
    "UPDATE wallets SET balance = balance + 10.00 WHERE user_id = ?",
    (vt['user_id'],)
)
db.commit()
```

## 10. Regression Validation

**Test:** `tests/test_lab_19.py`

- **Vulnerable mode:** Non-atomic verification allows token reuse or duplicate credits.
- **Patched mode:** Atomic conditional token update ensures second redemption returns HTTP 400 (`already used`).
- **Legitimate flow:** Single verification token redemption successfully credits wallet by $10.00.

## 11. Research Discussion

1. Why must the state transition marking a token as consumed always precede or accompany the side-effect action?
2. How does the "check-effects-interactions" pattern in smart contract design mirror TOCTOU prevention in web applications?
3. What database transaction isolation level is required to prevent phantom reads during token redemption?
