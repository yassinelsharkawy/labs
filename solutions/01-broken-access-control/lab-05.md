# Lab 5 — Stale Membership Resource Access

## 1. Objective

Demonstrate how failing to verify the active status flag of team memberships allows deactivated team members to retain unauthorized access to team-restricted resources.

## 2. Scenario

A project collaboration tool manages team memberships with an `active` status flag (`1` for active, `0` for removed or deactivated). When an employee or collaborator is removed from a team, the record remains in `team_members` with `active = 0` for audit purposes. However, the document retrieval handler only checks whether a membership record exists, neglecting the `active` status flag.

**Trust boundary:** The application assumed that existence of a membership row implied current authorized membership.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target user | `carol` / `carol123` (user ID 4, removed from Team 1) |
| Membership state | `active = 0` in `team_members` for team ID 1 |
| Target resource | Team 1 documents |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The vulnerable route queries membership existence without validating active status:

```sql
SELECT role FROM team_members WHERE team_id = ? AND user_id = ?
```

Because Carol's row is present in `team_members`, this query returns a row, and the endpoint authorizes access.

## 5. Reproduction

1. Authenticate as deactivated user `carol`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=carol&password=carol123"
```

2. Request documents belonging to Team 1:

```bash
curl -b cookies.txt http://localhost:5000/lab/bac/bac-05/team/1/documents
```

3. Observe that Team 1 documents are returned successfully despite Carol's deactivated status.

## 6. Evidence

The response returns confidential Team 1 project documents:

```json
[
  {
    "id": 1,
    "title": "Q3 Financial Report"
  },
  {
    "id": 2,
    "title": "Project Alpha Specs"
  }
]
```

## 7. Root Cause

**File:** `app/routes/bac.py`  
**Function:** `lab05_team_documents()`

In unpatched mode, the handler does not filter by active membership status:

```python
membership = db.execute(
    "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
    (team_id, session['user_id'])
).fetchone()
```

## 8. Impact

Former employees, offboarded contractors, or removed collaborators retain persistent access to internal organizational data and intellectual property.

## 9. Remediation

Include the `active = 1` condition in the membership authorization query:

```python
membership = db.execute(
    "SELECT role FROM team_members WHERE team_id = ? AND user_id = ? AND active = 1",
    (team_id, session['user_id'])
).fetchone()
```

## 10. Regression Validation

**Test:** `tests/test_lab_05.py`

- **Vulnerable mode:** Deactivated user Carol accesses Team 1 documents → HTTP 200.
- **Patched mode:** Deactivated user Carol accesses Team 1 documents → HTTP 403.
- **Legitimate flow:** Active member Alice accesses Team 1 documents → HTTP 200.

## 11. Research Discussion

1. What are the common causes of authorization discrepancies when user accounts or team memberships are soft-deleted?
2. How should session invalidation and caching layers synchronize with membership status updates?
3. How can database constraints and relational models help enforce active membership semantics automatically?
