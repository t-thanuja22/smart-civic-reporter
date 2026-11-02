# Test Plan -- Smart Civic Reporter
### Subject: Software Testing & Automation | Project: AI-Based Automated Testing Framework for Smart Civic Reporter Application

## 1. Objective
Design and execute an automated test suite -- unit, functional/API, and UI (end-to-end) --
for the Smart Civic Reporter web application, and use a machine-learning model to
prioritize which tests run first based on historical failure risk.

## 2. Test Levels & Tools
| Level | Tool | File |
|---|---|---|
| Unit testing | pytest | `tests/test_categorizer.py` |
| Functional / API testing | pytest + Flask test client | `tests/test_api.py` |
| System / UI (end-to-end) testing | Selenium WebDriver + pytest | `tests/test_selenium_ui.py` |
| Test prioritization (AI layer) | scikit-learn RandomForest | `tests/ai_test_prioritizer.py` |

## 3. Sample Test Case Matrix
| ID | Module | Test Case | Expected Result | Type |
|----|--------|-----------|------------------|------|
| TC-01 | Categorizer | Streetlight keyword text | category = Streetlight Fault, dept = EB | Unit |
| TC-02 | Categorizer | Electrical hazard keyword text | priority = Critical | Unit |
| TC-03 | Categorizer | Duplicate detection, 5m apart | second merges into first | Unit |
| TC-04 | Auth | Citizen login with worker credentials | rejected, redirected to correct portal | Security / Negative |
| TC-05 | Authorization | Worker views another department's complaint | access denied | Security / Negative |
| TC-06 | Complaint | Submit with dropdown category selected | dropdown overrides NLP guess | Functional / Positive |
| TC-07 | Complaint | Submit with voice note attached | complaint created, voice note stored | Functional / Positive |
| TC-08 | Status | Invalid status jump (Pending -> Completed directly) | rejected | Functional / Negative |
| TC-09 | Feedback | Rate a complaint before it's Completed | rejected | Functional / Negative |
| TC-10 | Feedback | Rate a Completed complaint | rating saved, shown on detail page | Functional / Positive |
| TC-11 | Notifications | Status changed by admin/worker | Notification row created for the citizen | Functional / Positive |
| TC-12 | Notifications | Citizen visits `/notifications` | list shown, unread count cleared | Functional / Positive |
| TC-13 | Notifications | Worker/admin visits `/notifications` | rejected -- citizens only | Security / Negative |
| TC-14 | Analytics | Citizen visits `/admin/analytics` | rejected -- admin only | Security / Negative |
| TC-15 | Analytics | Admin visits `/admin/analytics` | charts render with correct aggregate counts | Functional / Positive |
| TC-16 | Public Map | Anonymous visitor loads `/map` | page loads without login, pins fetched via API | Functional / Positive |
| TC-17 | UI (Selenium) | End-to-end submission | registers, logs in, lands on complaints page | System |
| TC-18 | API | `GET /api/complaints` | HTTP 200, JSON array | API |
| TC-19 | AI Prioritizer | Rank tests by risk | flaky/high-risk tests ranked first | ML validation |

## 4. Entry / Exit Criteria
- **Entry:** `pytest tests/test_categorizer.py` passes (no DB/server needed).
- **Exit:** all unit + functional tests pass, Selenium smoke suite passes against a running
  server, code coverage on `categorizer.py` and `app.py` >= 80%.

## 5. How this maps to your project title
"AI-based" = `ai_test_prioritizer.py` (ML-driven test ordering by predicted failure risk).
"Automated Testing Framework" = the pytest + Selenium suite under `tests/`.
"Smart Civic Reporter Application" = the system under test, in the project root.
