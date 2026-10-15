# Security Research Labs

> **Description:**  
> A Security Research Labs curriculum featuring original, isolated lab environments derived from vulnerability patterns observed in real-world security research.

---

## 1. Overview & Pedagogical Philosophy

The **Security Research Labs** is an educational framework designed for university classrooms, security engineering training, and defensive security research. The curriculum features **25 isolated laboratory environments** categorized into **5 foundational vulnerability classes**.

This curriculum bridges the gap between abstract software security concepts and production application realities. Rather than presenting isolated synthetic puzzles, each lab models a realistic software engineering design pattern containing an architectural, logical, or state-machine flaw commonly identified during web security audits. 

Every lab is built around a **dual-mode implementation** toggled by a central configuration flag (`PATCHED_MODE`), allowing learners and instructors to observe vulnerable behavior, test exploit mechanics, enable defensive remediations, and verify fix efficacy dynamically.

### Core Learning Objectives
Upon completing this curriculum, learners will be able to:
1. **Identify Architectural Trust Boundary Failures:** Recognize when application components assume safety instead of enforcing explicit authorization invariants.
2. **Execute Controlled Vulnerability Verification:** Write deterministic reproduction scripts that prove vulnerability existence without relying on disruptive attacks.
3. **Formulate Defense-in-Depth Remediations:** Design and implement cryptographic, transactional, and architectural mitigations that resolve root causes while maintaining business requirements.
4. **Evaluate Patch Robustness:** Verify that security controls eliminate unintended side-effects while fully preserving legitimate user workflows.

---

## 2. Labs Curriculum Structure & Roadmap

The curriculum is structured into 5 core vulnerability classes, containing 5 dedicated labs each:

### Class 1: Broken Access Control and IDOR (Labs 1–5)
- **Lab 1:** Tenant Isolation Bypass via Insecure Direct Object Reference (`CWE-639`)
- **Lab 2:** Insecure Direct Object Reference in Document Deletion (`CWE-639`)
- **Lab 3:** Export Endpoint Authorization Bypass (`CWE-639`)
- **Lab 4:** Privilege Escalation via Bulk Role Assignment (`CWE-269`)
- **Lab 5:** Stale Membership Resource Access (`CWE-285`)
- **Concepts:** Multi-tenancy, object ownership matrices, vertical role validation, active status filtering.
- **Key Focus:** Emphasize that parameter authentication does not equal authorization. learners frequently conflate valid session state with object permission.

### Class 2: Authentication, Sessions, and MFA (Labs 6–10)
- **Lab 6:** MFA Enforcement Bypass via Legacy API Endpoint (`CWE-306`)
- **Lab 7:** Password Reset Token Reuse After Password Change (`CWE-613`)
- **Lab 8:** Session Persistence After Password Change (`CWE-613`)
- **Lab 9:** OTP Replay and Non-Consumption (`CWE-287`)
- **Lab 10:** OAuth State Parameter Fixation (`CWE-352`)
- **Concepts:** API parity, session state lifecycle, global invalidation, OTP token consumption, OAuth state fixation.
- **Key Focus:** State machines. Walk learners through drawing sequence diagrams for multi-device session management and token lifecycles before examining code.

### Class 3: Injection: Cross-site scripting (XSS) and SQL Injection (Labs 11–15)
- **Lab 11:** Stored Cross-site scripting (XSS) in User Comments Rendered in Admin Panel (`CWE-79`)
- **Lab 12:** Reflected Cross-site scripting (XSS) via Search Redirect Parameter (`CWE-79`)
- **Lab 13:** Stored Cross-site scripting (XSS) via Wiki Page Markup (`CWE-79`)
- **Lab 14:** SQL Injection in Product Search Filter (`CWE-89`)
- **Lab 15:** Blind SQL Injection in Audit Log Query (`CWE-89`)
- **Concepts:** Contextual output encoding, URI protocol sanitization, UNION projection, blind boolean subqueries.
- **Key Focus:** Input validation vs. context-aware output encoding vs. parameterized queries. Demonstrate why string concatenation fundamentally violates data/instruction separation.

### Class 4: Business Logic and Race Conditions (Labs 16–20)
- **Lab 16:** Coupon Code Multiple Redemption (`CWE-362`)
- **Lab 17:** Concurrent Duplicate Refund Processing (`CWE-362`)
- **Lab 18:** Invitation Acceptance Exceeding Seat Limit (`CWE-362`)
- **Lab 19:** Parallel Verification Token Consumption (`CWE-362`)
- **Lab 20:** Subscription Downgrade State Inconsistency (`CWE-840`)
- **Concepts:** TOCTOU windows, transaction isolation levels (`BEGIN IMMEDIATE`), atomic conditional updates, lifecycle state consistency.
- **Key Focus:** Concurrency. learners often struggle to conceptualize race windows. Use concurrent request scripts to demonstrate race windows and parallel collision states.

### Class 5: Server-Side Request Forgery (Labs 21–25)
- **Lab 21:** Image Importer SSRF to Internal Metadata (`CWE-918`)
- **Lab 22:** Webhook Tester SSRF to Internal Services (`CWE-918`)
- **Lab 23:** Report Generator SSRF via Document URL (`CWE-918`)
- **Lab 24:** SSRF via Redirect Bypass of URL Allowlist (`CWE-918`)
- **Lab 25:** SSRF via URL Parsing Inconsistency (`CWE-918`)
- **Concepts:** Network egress boundaries, private IP space verification, DNS resolution, redirect validation, parser differential vulnerabilities.
- **Key Focus:** Defense-in-depth at network vs. application layers. Clarify why hostname allowlists fail without pre-request IP resolution and hop-by-hop redirect checks.

---

## 3. Architecture & Safety Isolation

- **Dual-Mode Execution:** The application evaluates `current_app.config['PATCHED_MODE']` at runtime. In vulnerable mode (`PATCHED_MODE=False`), the unmitigated flaw is active. In patched mode (`PATCHED_MODE=True`), defensive controls are enforced.
- **Safe Local Execution:** All network operations bind strictly to `127.0.0.1` locally or within the internal `labnet` Docker bridge network.
- **Mock Internal Endpoints:** Internal services and cloud metadata endpoints are emulated locally via `app/services/mock_internal.py` on port `5001`. No external network calls or third-party API keys are utilized.
- **Strict Anonymization:** All lab descriptions, parameters, scenarios, and database records use synthetic data, generic corporate schemas, and anonymized identifiers.

### Dual-Mode Demonstration
Instructors and learners can toggle between modes dynamically:

```bash
# Start application in default vulnerable mode:
python run.py

# Switch to patched remediation mode:
PATCHED_MODE=true python run.py
```

### Resetting Lab State
Because learners modify database records during exercises, a state reset mechanism is provided:
- **HTTP POST:** `http://127.0.0.1:5000/reset`
- **CLI Command:** `python -c "from app.database.db import reset_db; reset_db()"`

---

## 4. Quick Start & Setup

### Option A: Local Python Environment

1. **Clone and enter repository:**
   ```bash
   cd websec-research-labs
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux / macOS
   venv\Scripts\activate       # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database:**
   ```bash
   python -c "from app.database.db import reset_db; reset_db()"
   ```

5. **Run application servers:**
   - In terminal 1 (Lab Web Application on port 5000):
     ```bash
     python run.py
     ```
   - In terminal 2 (Mock Internal Service on port 5001):
     ```bash
     python mock_service.py
     ```

6. Open your browser to `http://127.0.0.1:5000`.

### Option B: Docker Compose

Launch the isolated multi-container environment:

```bash
docker compose up --build
```

Services started:
- `web`: Flask lab environment accessible at `http://127.0.0.1:5000`
- `mock-internal`: Emulated internal service on internal network `labnet` (port 5001)

---

## 5. Solution Manual Reference
Detailed solutions for all 25 labs adhering to a strict 11-section are located in `solutions/`:
- `solutions/01-broken-access-control/lab-01.md` through `lab-05.md`
- `solutions/02-authentication-sessions-mfa/lab-06.md` through `lab-10.md`
- `solutions/03-injection/lab-11.md` through `lab-15.md`
- `solutions/04-business-logic-race-conditions/lab-16.md` through `lab-20.md`
- `solutions/05-ssrf/lab-21.md` through `lab-25.md`

Each solution file provides:
1. Objective
2. Scenario
3. Preconditions
4. Vulnerability Mechanism
5. Reproduction Steps
6. Proof-of-Exploit Evidence
7. Root Cause Analysis
8. Impact Assessment
9. Remediation Implementation
10. Regression Validation
11. Real-World Research Discussion

---

## 6. Common Learner Misconceptions & Troubleshooting

1. **"Why did my IDOR exploit fail after another student ran their test?"**  
   *Root Cause:* SQLite database state was mutated.  
   *Remedy:* Have learners invoke `POST /reset` before executing reproduction steps.
2. **"Why is the concurrent race condition test failing intermittently?"**  
   *Root Cause:* SQLite WAL mode locking or thread context collisions.  
   *Remedy:* Ensure learners use thread-isolated clients inside worker threads rather than sharing a single client instance.
3. **"Why does my SSRF payload return 403 in patched mode even though I used a domain name?"**  
   *Root Cause:* The patched validator performs DNS resolution (`socket.getaddrinfo`) and verifies the underlying IP address against private subnets (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). Domain names that resolve to local interfaces are correctly blocked.
4. **"Does escaping input prevent SQL injection?"**  
   *Root Cause:* Conflating Cross-site scripting (XSS) defenses with SQLi defenses.  
   *Remedy:* Emphasize that parameterized queries (prepared statements) bind data to query parameters at the database protocol level, whereas escaping input strings is error-prone and context-dependent.

---

## 7. Educational Usage & Ethics

This curriculum is intended exclusively for authorized educational and research purposes:
- Classroom demonstrations.
- Defensive engineering training and code-auditing exercises.

All testing must be performed locally against the isolated environments provided.
