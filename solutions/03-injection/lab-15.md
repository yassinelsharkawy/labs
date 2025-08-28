# Lab 15 — Blind SQL Injection in Audit Log Query

## 1. Objective

Demonstrate how string concatenation within nested SQL subqueries enables boolean-based blind SQL injection to infer database information through conditional response differences.

## 2. Scenario

An internal compliance portal provides an audit log search interface allowing auditors to retrieve system activity events by username. The query searches for records matching a user ID resolved via a nested subquery. The username parameter is interpolated into the inner subquery without parameter binding. While database error messages are suppressed by a generic `try/except` block, true and false logical conditions yield distinguishable response sets.

**Trust boundary:** The application assumed that swallowing database exceptions prevents attackers from exploiting SQL syntax vulnerabilities.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/injection/inj-05/audit` |
| Vulnerable parameter | `username` (query string) |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The application constructs the SQL statement using string interpolation inside a subquery:

```python
query = (
    "SELECT a.id, a.action, a.detail, a.created_at "
    "FROM audit_log a WHERE a.user_id = "
    f"(SELECT id FROM users WHERE username = '{username}') "
    "ORDER BY a.created_at DESC"
)
```

By supplying a username that closes the subquery and appends a boolean expression (e.g. `admin') AND 1=1 --`), the attacker manipulates the resolution of the `WHERE` clause. When the condition evaluates to true, audit records are returned; when false, an empty array is returned.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Seed the audit log entries if not already populated:

```bash
curl -b cookies.txt http://localhost:5000/lab/injection/inj-05
```

3. Submit a request with a boolean-true condition:

```bash
curl -b cookies.txt "http://localhost:5000/lab/injection/inj-05/audit?username=admin%27%29%20AND%201%3D1%20--"
```

4. Submit a request with a boolean-false condition:

```bash
curl -b cookies.txt "http://localhost:5000/lab/injection/inj-05/audit?username=admin%27%29%20AND%201%3D2%20--"
```

5. Observe the differential response length.

## 6. Evidence

- **Condition 1=1 (True):** Returns HTTP 200 with matching audit log items:
  ```json
  [
    {"action": "login", "detail": "admin logged in", "id": 1, ...},
    {"action": "export", "detail": "admin exported user list", "id": 4, ...}
  ]
  ```
- **Condition 1=2 (False):** Returns HTTP 200 with an empty list:
  ```json
  []
  ```

This behavioral discrepancy allows an attacker to extract data bit-by-bit using iterative boolean questions.

## 7. Root Cause

**File:** `app/routes/injection.py`  
**Function:** `lab15_audit_search()`

The username input is interpolated directly into the subquery:

```python
if patched:
    rows = db.execute(
        "SELECT a.id, a.action, a.detail, a.created_at "
        "FROM audit_log a WHERE a.user_id = (SELECT id FROM users WHERE username = ?) "
        "ORDER BY a.created_at DESC",
        (username,),
    ).fetchall()
else:
    query = (
        "SELECT a.id, a.action, a.detail, a.created_at "
        "FROM audit_log a WHERE a.user_id = "
        f"(SELECT id FROM users WHERE username = '{username}') "
        "ORDER BY a.created_at DESC"
    )
    rows = db.execute(query).fetchall()
```

## 8. Impact

An attacker can infer database structure, enumerate sensitive columns, and extract secret tokens, password hashes, or confidential data by sending a series of boolean queries.

## 9. Remediation

Bind the username parameter using parameterized queries within the subquery:

```python
rows = db.execute(
    "SELECT a.id, a.action, a.detail, a.created_at "
    "FROM audit_log a WHERE a.user_id = (SELECT id FROM users WHERE username = ?) "
    "ORDER BY a.created_at DESC",
    (username,)
).fetchall()
```

## 10. Regression Validation

**Test:** `tests/test_lab_15.py`

- **Vulnerable mode:** `admin') AND 1=1 --` returns rows, while `admin') AND 1=2 --` returns 0 rows.
- **Patched mode:** Injected query payload is evaluated literally; returns 0 rows for non-existent username string.
- **Legitimate flow:** Searching for valid user `alice` returns audit records.

## 11. Research Discussion

1. What distinguishes boolean-based blind SQL injection from time-based blind SQL injection?
2. Why is error suppression insufficient as a defense against injection attacks?
3. How can database query monitoring and anomaly detection assist in identifying automated blind SQL injection scanning?
