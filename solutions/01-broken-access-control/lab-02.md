# Lab 2 — Unauthorized Document Deletion via API

## 1. Objective

Demonstrate how missing object-ownership validation on a state-modifying `DELETE` endpoint allows an authenticated user to delete documents belonging to another user.

## 2. Scenario

A document management application allows users to create, view, and manage private documents. While the document retrieval endpoint limits visibility to owned and explicitly shared files, the document deletion API route performs deletion solely by primary key (`id`) without verifying that the requesting user owns the target record.

**Trust boundary:** The application assumes that clients will only submit deletion requests for document IDs that they created.

## 3. Preconditions

| Item | Value |
|------|-------|
| Attacker account | `bob` / `bob123` (user ID 3) |
| Target data | Document ID 4 (`HR Policy Draft`, owned by user ID 4 `carol`) |
| Seed state | Initial database seed (`POST /reset`) |

Bob does not own Document 4 and is not included in Document 4's `shared_with` list.

## 4. Vulnerability Mechanism

The vulnerable endpoint executes an unqualified soft-delete update:

```sql
UPDATE documents SET deleted = 1 WHERE id = ?
```

Because the `WHERE` clause does not constrain the query with `AND owner_id = ?`, any authenticated caller can delete any document in the database simply by knowing or iterating the integer document ID.

## 5. Reproduction

1. Authenticate as `bob`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=bob&password=bob123"
```

2. Send a `DELETE` request for Document 4 (owned by `carol`):

```bash
curl -b cookies.txt -X DELETE http://localhost:5000/lab/bac/bac-02/documents/4
```

3. Verify that the server returns HTTP 200 confirming deletion.

## 6. Evidence

The response demonstrates that the deletion succeeded:

```json
{
  "document_id": 4,
  "status": "deleted"
}
```

A subsequent query for Document 4 confirms its `deleted` flag is set to `1`.

## 7. Root Cause

**File:** `app/routes/bac.py`  
**Function:** `lab02_delete_document()`

In unpatched mode, the application extracts `doc_id` from the path and executes:

```python
result = db.execute("UPDATE documents SET deleted = 1 WHERE id = ?", (doc_id,))
```

No validation is performed against `session['user_id']`.

## 8. Impact

An authenticated attacker can perform unauthorized data destruction across all user accounts, leading to data loss, service disruption, and integrity failure.

## 9. Remediation

Enforce ownership binding in the database update query:

```python
result = db.execute(
    "UPDATE documents SET deleted = 1 WHERE id = ? AND owner_id = ?",
    (doc_id, session['user_id'])
)
```

If `result.rowcount == 0`, return HTTP 404 to avoid leaking resource existence while denying unauthorized modification.

## 10. Regression Validation

**Test:** `tests/test_lab_02.py`

- **Vulnerable mode:** Bob deletes Document 4 → HTTP 200 with status `deleted`.
- **Patched mode:** Bob deletes Document 4 → HTTP 404 (unauthorized resource not found).
- **Legitimate flow:** Bob deletes Document 3 (his own document) → HTTP 200 in both modes.

## 11. Research Discussion

1. Why are object-level access controls frequently omitted on mutating operations (`DELETE`, `PUT`) even when properly applied on `GET` endpoints?
2. What are the security and operational trade-offs between returning HTTP 403 Forbidden vs. HTTP 404 Not Found for unauthorized object-level access attempts?
3. How can access control decorators or Object-Relational Mapping (ORM) scoping hooks systematically prevent object-level authorization omissions?
