# Lab 12 — Reflected XSS via Search Redirect Parameter

## 1. Objective

Demonstrate how reflecting unvalidated URL parameters into link navigation attributes permits reflected cross-site scripting (XSS) via pseudo-protocols like `javascript:`.

## 2. Scenario

An e-commerce product search interface accepts a query string `q` and an optional post-search navigation parameter `redirect_to`. The search results template renders the `redirect_to` parameter directly inside the `href` attribute of a "Return" hyperlink. Because the parameter is rendered without protocol validation, an attacker can specify a `javascript:` pseudo-protocol URL.

**Trust boundary:** The application assumed that URL parameters passed into navigation links would only contain HTTP or relative application paths.

## 3. Preconditions

| Item | Value |
|------|-------|
| Target endpoint | `/lab/injection/inj-02/search` |
| Vulnerable parameter | `redirect_to` |
| Seed state | Initial database seed (`POST /reset`) |

## 4. Vulnerability Mechanism

The server extracts `redirect_to` from the query string and passes it into the template context without validation. The template renders:

```html
<a id="return-link" href="{{ redirect_to }}">Continue to destination</a>
```

When an attacker supplies `redirect_to=javascript:alert(1)`, the resulting HTML element contains an executable JavaScript handler triggered upon clicking.

## 5. Reproduction

1. Log in as an authenticated user:

```bash
curl -c cookies.txt -X POST http://localhost:5000/login \
  -d "username=alice&password=alice123"
```

2. Request the search endpoint with a `javascript:` payload in `redirect_to`:

```bash
curl -b cookies.txt "http://localhost:5000/lab/injection/inj-02/search?q=Widget&redirect_to=javascript:alert(1)"
```

3. Examine the returned HTML to verify that the `href` attribute contains the JavaScript execution payload.

## 6. Evidence

The response HTML contains the reflected pseudo-protocol link:

```html
<a id="return-link" href="javascript:alert(1)">Continue to destination</a>
```

Clicking the link in a browser executes the JavaScript instruction within the victim's session.

## 7. Root Cause

**File:** `app/routes/injection.py`  
**Function:** `lab12_search()`

The handler does not enforce relative path or allowed scheme validation on `redirect_to` in vulnerable mode:

```python
if patched:
    if redirect_to and not redirect_to.startswith('/'):
        redirect_to = ''
```

## 8. Impact

An attacker can construct a phishing link that, when clicked by a victim, executes arbitrary script in the victim's authenticated session context.

## 9. Remediation

Strictly validate that redirection parameters begin with a single forward slash (`/`) and do not specify external schemes or protocol-relative targets (`//`):

```python
if redirect_to and (not redirect_to.startswith('/') or redirect_to.startswith('//')):
    redirect_to = ''
```

## 10. Regression Validation

**Test:** `tests/test_lab_12.py`

- **Vulnerable mode:** Search with `javascript:alert(1)` reflects `href="javascript:alert(1)"`.
- **Patched mode:** Search with `javascript:alert(1)` omits or clears the invalid destination.
- **Legitimate flow:** Relative redirection target (e.g., `/lab/injection/inj-02`) renders correctly.

## 11. Research Discussion

1. Why does traditional HTML entity encoding fail to prevent XSS when payloads are injected into URI attributes like `href` or `src`?
2. How should applications validate external redirect destinations to prevent both open redirection and URI-based XSS?
3. What browser security mechanisms (such as CSP `navigate-to` or modern sanitizers) mitigate attribute-level script execution?
