# Lab 13 — Stored XSS via Wiki Page Markup

## 1. Objective

Demonstrate how storing unvalidated HTML wiki markup and rendering it without rigorous sanitization or output escaping allows stored cross-site scripting (XSS).

## 2. Scenario

An internal team knowledge base allows authenticated employees to edit and view documentation wiki pages. Users can format their documents using HTML tags. When a wiki page is rendered, the application renders the stored database content directly into the view using the template's unescaped markup filter (`|safe`).

**Trust boundary:** The application assumed that wiki page authors are trusted or that rendering raw HTML tags without sanitizing active content (`<script>`, event handlers) is safe.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target page | `/lab/injection/inj-03/wiki/getting-started` |
| Edit endpoint | `/lab/injection/inj-03/wiki/getting-started/edit` |
| Authenticated user | `alice` / `alice123` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The wiki editing handler accepts raw text in the JSON body:

```sql
UPDATE wiki_pages SET body = ? WHERE slug = ?
```

When displaying the page, the server assigns the raw stored content directly to the rendering context:

```html
<div class="wiki-content">{{ page.body_html | safe }}</div>
```

Any embedded JavaScript elements or event handlers stored in the database are executed immediately by the browser when the page is viewed.

## 5. Reproduction

1. Authenticate as `alice`:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Update the `getting-started` wiki page with an active script tag:

```bash
curl -b cookies.txt -X POST http://localhost:5000/lab/injection/inj-03/wiki/getting-started/edit \
  -H "Content-Type: application/json" \
  -d '{"body": "<h2>Title</h2><script>alert(\"wiki-xss\")</script>"}'
```

3. View the wiki page:

```bash
curl -b cookies.txt http://localhost:5000/lab/injection/inj-03/wiki/getting-started
```

4. Verify that the response body contains the unescaped script tag.

## 6. Evidence

The response HTML contains the raw, unescaped script:

```html
<div class="wiki-content"><h2>Title</h2><script>alert("wiki-xss")</script></div>
```

Any user navigating to `/lab/injection/inj-03/wiki/getting-started` will execute the injected script.

## 7. Root Cause

**File:** `app/routes/injection.py`  
**Function:** `lab13_wiki_view()`

In vulnerable mode, `page_dict['body_html']` is assigned the raw database string without stripping active script tags or escaping dangerous attributes:

```python
if patched:
    body = page_dict['body']
    body = re.sub(r'<\s*script[^>]*>.*?</\s*script\s*>', '', body, flags=re.I | re.S)
    body = re.sub(r'\bon\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', '', body, flags=re.I)
    page_dict['body_html'] = str(html_escape(body))
else:
    page_dict['body_html'] = page_dict['body']
```

## 8. Impact

Any user who views the wiki page is subjected to arbitrary JavaScript execution in their browser, enabling session hijacking, document alteration, or credential theft.

## 9. Remediation

Strip active script tags, dangerous HTML attributes (such as `onload`, `onerror`, `onclick`), and apply output entity escaping, or utilize a robust HTML sanitizer library (such as Bleach with a strict tag and attribute whitelist):

```python
import re
from markupsafe import escape as html_escape

body = page_dict['body']
body = re.sub(r'<\s*script[^>]*>.*?</\s*script\s*>', '', body, flags=re.I | re.S)
body = re.sub(r'\bon\w+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', '', body, flags=re.I)
page_dict['body_html'] = str(html_escape(body))
```

## 10. Regression Validation

**Test:** `tests/test_lab_13.py`

- **Vulnerable mode:** Stored wiki update containing `<script>` renders raw script tag in HTML view.
- **Patched mode:** Injected payload has `<script>` tags and `onerror=` handlers stripped and escaped.
- **Legitimate flow:** Benign documentation text renders cleanly without alteration.

## 11. Research Discussion

1. Why are client-side rich text editors and Markdown renderers frequent sources of stored XSS vulnerabilities?
2. What are the limitations of regular expression-based HTML sanitization compared to DOM-based parsing?
3. How can `sandbox` attributes on `<iframe>` elements isolate user-generated rich markup from the parent origin?
