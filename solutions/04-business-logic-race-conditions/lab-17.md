# Lab 17 — Concurrent Duplicate Refund Processing

## 1. Objective

Demonstrate how race conditions in order refund workflows allow duplicate balance credits for a single purchase order when transactions are not serialized.

## 2. Scenario

An online store allows customers to request refunds for completed orders. When an order refund is requested, the system verifies that `status == 'completed'`, records a refund entry, increments the customer's wallet balance by the order amount, and marks the order status as `'refunded'`. Because the refund record and wallet credit occur prior to updating the order status without transaction serialization, parallel refund requests can execute simultaneously.

**Trust boundary:** The application assumed that check-then-act sequences within standard database transactions execute without interference from concurrent threads.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/logic/logic-02/refund` |
| Test order | Order ID `1` (Amount: `49.99`, User: `alice`) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /lab/logic/logic-02/reset`) |

## 4. Vulnerability Mechanism

The vulnerable endpoint checks eligibility:

```sql
SELECT * FROM orders WHERE id = ?
```

If `order['status'] == 'completed'`, it processes the refund:

```sql
INSERT INTO refunds (order_id, amount, status) VALUES (?, ?, 'processed')
UPDATE wallets SET balance = balance + ? WHERE user_id = ?
UPDATE orders SET status = 'refunded' WHERE id = ?
```

Because the status update occurs at the end of the operation and transactions are not serialized with `BEGIN IMMEDIATE`, two concurrent requests can both read `status == 'completed'` before either marks it as `'refunded'`, crediting the user's wallet twice.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Reset order and wallet state:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-02/reset
```

3. Trigger concurrent refund requests for order 1:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-02/refund \
  -H "Content-Type: application/json" \
  -d '{"order_id": 1}' &
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-02/refund \
  -H "Content-Type: application/json" \
  -d '{"order_id": 1}' &
wait
```

4. Inspect wallet balance and refund logs:

```bash
curl -b cookies.txt http://localhost:5000/lab/logic/logic-02/orders
```

## 6. Evidence

The orders inspection endpoint reveals multiple processed refund records and inflated wallet balance:

```json
{
  "refunds": [
    {"amount": 49.99, "id": 1, "order_id": 1, "status": "processed"},
    {"amount": 49.99, "id": 2, "order_id": 1, "status": "processed"}
  ]
}
```

The wallet received $99.98 in credits for a single $49.99 purchase order.

## 7. Root Cause

**File:** `app/routes/logic.py`  
**Function:** `lab17_refund()`

In vulnerable mode, the status check and wallet credit operations are executed without acquiring an exclusive write lock at the start of the transaction:

```python
if patched:
    db.execute("BEGIN IMMEDIATE")
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order['status'] != 'completed':
        db.rollback()
        return jsonify({'error': 'Order not eligible for refund'}), 400
    db.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
    # ... credit wallet and insert refund ...
    db.commit()
```

## 8. Impact

Attackers can duplicate refunds, drain application funds, or manipulate digital asset balances through automated burst requests.

## 9. Remediation

Acquire an immediate exclusive transaction lock or utilize optimistic concurrency control (`UPDATE orders SET status = 'refunded' WHERE id = ? AND status = 'completed'`):

```python
db.execute("BEGIN IMMEDIATE")
order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
if not order or order['status'] != 'completed':
    db.rollback()
    return jsonify({'error': 'Order not eligible for refund'}), 400

db.execute("UPDATE orders SET status = 'refunded' WHERE id = ?", (order_id,))
db.execute("INSERT INTO refunds (order_id, amount, status) VALUES (?, ?, 'processed')", (order_id, order['amount']))
db.execute("UPDATE wallets SET balance = balance + ? WHERE user_id = ?", (order['amount'], order['user_id']))
db.commit()
```

## 10. Regression Validation

**Test:** `tests/test_lab_17.py`

- **Vulnerable mode:** Sequential/concurrent operations allow non-atomic refund status processing.
- **Patched mode:** First refund marks status `refunded`; second attempt fails with HTTP 400 (`not eligible`).
- **Legitimate flow:** Single legitimate refund completes and updates wallet balance accurately.

## 11. Research Discussion

1. How do database isolation levels (`READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`) affect race condition vulnerability surfaces?
2. What is the role of idempotency keys in financial payment processing APIs (e.g. Stripe Idempotency-Key headers)?
3. Why should state transitions (e.g., `completed` → `refunded`) be enforced via database constraints or atomic conditional statements rather than application-layer checks?
