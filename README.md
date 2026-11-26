# ROA Automation

## Files

```
config.py          settings: URL, wait times, OTP, password
dummy_data.py      values typed into forms + new name/email/phone each run
email_counter.txt  \ counters for the next name / phone (only go up)
phone_counter.txt  /
pages/             one file per screen of the website
   base_page.py    common actions: click, fill, dropdown, popup, OTP, calendar
   signup_page.py, roa_application_page.py, tax_information_page.py,
   sign_ica_page.py, agent_tools_page.py, payment_page.py,
   roa_email_page.py, transfer_license_page.py, login_page.py
   admin_login_page.py   admin site login (email + OTP)
   admin_agent_page.py   admin: find agent > Transfer now > Onboard Agent > check Active
tests/
   regression.py      regression test cases
                      test_01 = 'Onboarding without Sponsor and Team' (happy flow), one block per test case
                      (newly licensed agent without license number, no sponsor, no team)
test_cases/
   agent_onboarding_happy_flow.csv   the test case sheet (TC ID, Stage, Scenario, Expected, Priority)
testcase_tracker.py  links each `with tc("TC_AO_001"):` block to a row of the sheet
test_data/           files the tests upload (license_document.pdf)
created_users.csv  list of every user the test created (with PASSED / FAILED)
dashboard.py       builds reports/dashboard.html after each run (no need to touch)
conftest.py        browser setup, steps, --users, result summary (no need to touch)
pytest.ini         pytest options (no need to touch)
reports/           dashboard.html, testcase_results.csv, screenshot when a test fails
```

## Run

```powershell
.\venv1\Scripts\activate
pytest                          # browser visible
pytest --users 3                # create 3 users (runs the test 3 times)
$env:HEADLESS="1"; pytest       # no browser window
```

While running, the terminal shows each step:
```
[STEP 4] Sign ICA ... done (52s)
```
At the end you get a result per test (and the step where it failed):
```
Test case 1 - Onboarding (user 2) ........ FAILED at 'Sign ICA'  (2m 54s)
      user: Easton Weaver | easton.weaver@mailinator.com | 6465550169
```
Every created user is added to `created_users.csv` (open it in Excel).

### Test cases
Every row of `test_cases/agent_onboarding_happy_flow.csv` is checked in `tests/regression.py`:
```python
with tc("TC_AO_025"):
    tc.see("Congrats", user["full_name"], "Continue: Tax Information")   # texts on screen
    tc.progress(70)                                                        # progress circle %
    tc.check(a == b, "what is wrong")                                     # any other check
```
- A failed check marks the test case **FAILED** and the run continues.
- If an action fails (button missing, page did not open) the run stops and every test case after it is **BLOCKED**.
- **SKIPPED** = not automated (TC_AO_003: staging uses a fixed OTP, the inbox is not read).

Results per test case: on the dashboard and in `reports/testcase_results.csv`
(same columns as the sheet, with *Actual Result* and *Status* filled in - open it in Excel).

Debug a screen: `$env:TC_DUMP="1"; pytest` saves a screenshot + page text/HTML of every test case to `reports/tc_dump/`.

### Dashboard
After every run `reports/dashboard.html` is created and opens in your browser:
test case results (click Passed / Failed / Blocked / Skipped to filter, results per stage), pass/fail cards, time per step, trend of the last 30 runs, every run with its error and
a screenshot when it failed. History is kept in `reports/history.json`
(turn off auto-open with `OPEN_DASHBOARD = False` in `config.py`).

## Add something new (3 steps)

1. Create `pages/my_page.py`:
   ```python
   from pages.base_page import BasePage

   class MyPage(BasePage):
       def complete(self):
           self.wait_for_page("/my-page")
           self.fill(self.input("first_name"), "James")
           self.click(self.button("Save"))
   ```
2. Create `tests/test_my_page.py` (file and function names must start with `test_`):
   ```python
   from pages.login_page import LoginPage
   from pages.my_page import MyPage

   def test_my_page(page):
       LoginPage(page).login("ava.morgan@mailinator.com")
       MyPage(page).complete()
   ```
3. Run it: `pytest tests/test_my_page.py`
