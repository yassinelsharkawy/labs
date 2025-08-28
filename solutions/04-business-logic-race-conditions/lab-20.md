# Lab 20 — Subscription Downgrade State Inconsistency

## 1. Objective

Demonstrate how inconsistent state evaluation between subscription cancellation flags and feature authorization checks allows canceled subscribers to retain premium access.

## 2. Scenario

A SaaS application offers tiered subscription plans (`pro` and `free`). Users on the `pro` plan have access to premium features (e.g. `premium_export`). When a user requests cancellation of their subscription, the system marks the record with `cancel_requested = 1`. In unpatched mode, the feature gating endpoint (`/use-feature`) validates only whether `plan == 'pro'` without verifying the `cancel_requested` flag, allowing users with pending cancellations to access paid functionality.

**Trust boundary:** The application assumed that checking subscription tier name (`plan`) was sufficient to determine entitlement without validating subscription status and cancellation lifecycle flags.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/logic/logic-05/use-feature` |
| Cancellation endpoint | `/lab/logic/logic-05/cancel` |
| User subscription | Subscription ID `1` (Alice, `pro` tier) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /lab/logic/logic-05/reset`) |

## 4. Vulnerability Mechanism

The feature gating handler checks authorization using only the plan column:

```python
sub = db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
if sub['plan'] != 'pro':
    return jsonify({'error': 'Premium feature not available'}), 403
```

Because `sub['cancel_requested']` is not evaluated, any subscription where `cancel_requested == 1` while `plan == 'pro'` (such as during grace periods or intermediate processing) continues to pass the authorization check.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Reset subscription state:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-05/reset
```

3. Initiate subscription cancellation:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-05/cancel \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": 1}'
```

4. If `cancel_requested = 1` while tier is preserved, request premium feature access:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/logic/logic-05/use-feature \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": 1}'
```

## 6. Evidence

The feature endpoint returns HTTP 200 indicating successful execution of the premium action:

```json
{
  "feature": "premium_export",
  "plan": "pro",
  "status": "feature_used",
  "subscription_id": 1
}
```

The user retained premium feature execution despite having initiated cancellation.

## 7. Root Cause

**File:** `app/routes/logic.py`  
**Function:** `lab20_use_feature()`

In vulnerable mode, the access check only verifies the `plan` column and ignores lifecycle state:

```python
if patched:
    if sub['plan'] != 'pro' or sub['cancel_requested'] == 1:
        return jsonify({'error': 'Premium feature not available'}), 403
else:
    if sub['plan'] != 'pro':
        return jsonify({'error': 'Premium feature not available'}), 403
```

## 8. Impact

Users can access paid features indefinitely after cancelling their subscriptions, avoiding billing obligations.

## 9. Remediation

Evaluate all relevant subscription status flags, verifying both active tier and the absence of cancellation flags:

```python
if sub['plan'] != 'pro' or sub['cancel_requested'] == 1 or sub['status'] != 'active':
    return jsonify({'error': 'Premium feature not available'}), 403
```

Ensure cancellation updates both fields atomically in a single statement:

```python
db.execute(
    "UPDATE subscriptions SET cancel_requested = 1, plan = 'free' WHERE id = ?",
    (sub_id,)
)
db.commit()
```

## 10. Regression Validation

**Test:** `tests/test_lab_20.py`

- **Vulnerable mode:** Access granted when `cancel_requested = 1` and `plan = 'pro'`.
- **Patched mode:** Access denied with HTTP 403 when `cancel_requested == 1`.
- **Legitimate flow:** Active `pro` subscriber with no pending cancellation accesses feature successfully.

## 11. Research Discussion

1. Why are finite-state machines (FSMs) beneficial for managing subscription and billing lifecycles?
2. What synchronization challenges arise when subscription states are shared between payment processors (e.g. Stripe webhooks) and application databases?
3. How can feature flags and entitlement services prevent state divergence across distributed microservices?
