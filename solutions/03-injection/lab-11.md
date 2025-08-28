# Lab 11 — Stored XSS in User Comments Rendered in Admin Panel

## 1. Objective

Demonstrate how unescaped user-supplied content stored in a database and subsequently rendered in an administrative dashboard leads to stored cross-site scripting (XSS).

## 2. Scenario

A web platform allows authenticated users to submit comments on posts. An internal administrative moderation dashboard renders pending comments for administrative review. While the user-facing comment view escapes special characters, the administrative template marks comment content with `|safe`, allowing arbitrary HTML and script tags to execute in the administrator's browser context.

**Trust boundary:** The application assumed that content displayed in administrative interfaces did not require output encoding.

## 3. Preconditions

| Item | Value |
|------|-------|
| Attacker account | `alice` / `alice123` |
| Moderation view | `/lab/injection/inj-01/admin-view` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The comment submission route inserts raw user text into the `comments` table without sanitization:

```sql
INSERT INTO comments (user_id, target_type, target_id, body) VALUES (?, 'post', 0, ?)
```

The administrative view passes the raw string to the template:

```html
<div class="comment-body">{{ c.body_html | safe }}</div>
```

Because `body_html` contains raw script markup, the browser executes the script when the page renders.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Submit a comment containing a script payload:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/injection/inj-01/comments \
  -H "Content-Type: application/json" \
  -d '{"body": "<script>alert(\"stored-xss\")</script>"}'
```

3. Access the administrative moderation panel:

```bash
curl -b cookies.txt http://localhost:5000/lab/injection/inj-01/admin-view
```

4. Observe unescaped `<script>` tags present in the returned HTML document.

## 6. Evidence

The administrative view response contains the literal, unescaped payload:

```html
<div class="comment-body"><script>alert("stored-xss")</script></div>
```

## 7. Root Cause

**File:** `app/routes/injection.py`  
**Function:** `lab11_admin_view()`

In vulnerable mode, `body_html` is populated with raw database text without entity escaping:

```python
if patched:
    d['body_html'] = str(html_escape(d['body']))
else:
    d['body_html'] = d['body']
```

## 8. Impact

An unprivileged user can execute arbitrary JavaScript in the context of an administrator, potentially leading to session hijacking, credential theft, or unauthorized administrative actions.

## 9. Remediation

Apply contextual HTML entity escaping before rendering untrusted content:

```python
from markupsafe import escape as html_escape

d['body_html'] = str(html_escape(d['body']))
```

Ensure templates avoid using the `|safe` filter on user-controllable data.

## 10. Regression Validation

**Test:** `tests/test_lab_11.py`

- **Vulnerable mode:** Admin view contains raw `<script>` tag → Present.
- **Patched mode:** Admin view contains `&lt;script&gt;` entity representation → Script tag absent.
- **Legitimate flow:** Benign text comment renders successfully in both modes.

## 11. Research Discussion

1. Why are administrative panels and back-office portals common vectors for second-order injection attacks?
2. How does Content Security Policy (CSP) provide defense-in-depth against stored XSS execution?
3. What are the distinctions between input sanitization, input validation, and context-aware output encoding?
