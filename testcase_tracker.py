# ============================================================
# TEST CASE TRACKER - links the automation to the test case sheet
#   test_cases/<sheet>.csv  ->  TC ID, Stage, Page, Scenario, Expected Result, Priority
#
#   with tc("TC_AO_001"):                          # one block per test case
#       with tc.step("Open the sign-up page"):     # an action (sub-case). If it fails the run stops
#           signup.open_sign_up()                  #   and every test case after it = BLOCKED
#       tc.see("Create an Account")                # check (sub-case): text is shown
#       tc.check(x == y, "6 OTP boxes", f"{x}")    # check (sub-case): name + what was found
#       tc.progress(20)                            # check (sub-case): progress circle = 20%
#
# A failed check marks the test case FAILED but the run keeps going.
# Every step and check is saved as a sub-case and shown on the dashboard.
#
# Status:  PASSED | FAILED | BLOCKED (an earlier step failed) | SKIPPED (not automated)
# ============================================================
import csv
import os
import re
import time
from contextlib import contextmanager

from config import DEFAULT_TIMEOUT

PROJECT = os.path.dirname(os.path.abspath(__file__))
DUMP_DIR = os.path.join(PROJECT, "reports", "tc_dump") if os.getenv("TC_DUMP") == "1" else None


def load_test_cases(sheet):
    path = os.path.join(PROJECT, "test_cases", sheet)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{"id": r["TC ID"], "stage": r["Stage"], "page": r["Page / Screen"], "scenario": r["Test Scenario"],
                 "expected": r["Expected Result"], "priority": r["Priority"]} for r in csv.DictReader(f)]


class TestCaseTracker:
    def __init__(self, page, sheet):
        self.page = page
        self.sheet = sheet
        self.cases = {c["id"]: {**c, "status": "NOT RUN", "actual": "", "seconds": 0, "checks": []}
                      for c in load_test_cases(sheet)}
        self.current = None
        self.stopped = False

    # ---------- one test case ----------
    @contextmanager
    def __call__(self, tc_id):
        case = self.cases[tc_id]          # KeyError = TC ID not in the sheet
        self.current = case
        case["checks"] = []
        start = time.time()
        print(f"  {tc_id} {case['scenario']} ...", end=" ", flush=True)
        if DUMP_DIR:
            self.dump(tc_id)
        try:
            yield case
        except BaseException as e:
            if not any(c["status"] == "FAILED" and c["kind"] == "step" for c in case["checks"]):
                self._add("step", "Run test case", "FAILED", short_error(e))     # error outside a tc.step
            case["status"] = "FAILED"
            case["actual"] = self._problems(case)
            case["seconds"] = round(time.time() - start, 1)
            self.stopped = True
            print("FAILED")
            raise
        finally:
            self.current = None
        case["seconds"] = round(time.time() - start, 1)
        problems = self._problems(case)
        if problems:
            case["status"] = "FAILED"
            case["actual"] = problems
            print("FAILED:", problems)
        else:
            case["status"] = "PASSED"
            case["actual"] = case.get("note") or "As expected"
            print(f"passed ({case['seconds']}s)")

    def skip(self, tc_id, reason):
        self.cases[tc_id].update(status="SKIPPED", actual=reason,
                                 checks=[{"kind": "info", "name": reason, "status": "SKIPPED", "detail": "",
                                          "seconds": 0}])
        print(f"  {tc_id} skipped: {reason}")

    def note(self, text):
        """Extra info shown in 'Actual Result' when the test case passes."""
        self.current["note"] = text
        self._add("info", text, "INFO")

    # ---------- sub-cases ----------
    def _add(self, kind, name, status, detail="", seconds=0):
        self.current["checks"].append({"kind": kind, "name": name, "status": status, "detail": detail,
                                       "seconds": round(seconds, 1)})

    @staticmethod
    def _problems(case):
        return "; ".join(f"{c['name']}: {c['detail']}" if c["detail"] else c["name"]
                         for c in case["checks"] if c["status"] == "FAILED")

    @contextmanager
    def step(self, name):
        """An action (click, fill, submit...). Recorded as a sub-case; an error stops the run."""
        start = time.time()
        try:
            yield
        except BaseException as e:
            self._add("step", name, "FAILED", short_error(e), time.time() - start)
            raise
        self._add("step", name, "PASSED", "", time.time() - start)

    # ---------- checks (record the result, keep going) ----------
    def check(self, condition, name, actual=""):
        """name = what should be true ('6 OTP boxes shown'); actual = what was found (shown when it fails)."""
        self._add("check", name, "PASSED" if condition else "FAILED", "" if condition else str(actual))
        return bool(condition)

    def see(self, *texts, timeout=10_000, root=None):
        """Check every text is visible. The first one may wait for the page; the others only briefly."""
        root = root or self.page
        for i, text in enumerate(texts):
            label = text if isinstance(text, str) else text.pattern
            loc = root.get_by_text(text).filter(visible=True).first
            try:
                loc.wait_for(state="visible", timeout=timeout if i == 0 else 3_000)
                self._add("check", f"Shows '{label}'", "PASSED")
            except Exception:
                self._add("check", f"Shows '{label}'", "FAILED", "not found on the screen")

    def see_element(self, locator, name, timeout=3_000):
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            self._add("check", f"Shows {name}", "PASSED")
            return True
        except Exception:
            self._add("check", f"Shows {name}", "FAILED", "not found on the screen")
            return False

    def progress(self, expected, timeout=10_000):
        """Left panel progress circle, e.g. 45%. Waits a little because it updates after the page."""
        value = None
        end = time.time() + timeout / 1000
        while time.time() < end:
            value = read_progress(self.page)
            if value == expected:
                break
            self.page.wait_for_timeout(300)
        self.check(value == expected, f"Progress shows {expected}%", f"shows {value}%")

    def on_page(self, path, name=None, timeout=DEFAULT_TIMEOUT):
        """Wait for the URL to contain path (a step: stops the run if the page never opens)."""
        with self.step(name or f"Opens page {path}"):
            self.page.wait_for_url(f"**{path}**", timeout=timeout, wait_until="commit")

    def dump(self, name):
        """Debug: $env:TC_DUMP="1" saves a screenshot + page text/HTML when each test case starts."""
        os.makedirs(DUMP_DIR, exist_ok=True)
        base = os.path.join(DUMP_DIR, name)
        try:
            self.page.screenshot(path=base + ".png", full_page=True, timeout=10_000)
            with open(base + ".txt", "w", encoding="utf-8") as f:
                f.write(self.page.url + "\n\n" + self.page.inner_text("body", timeout=5_000))
            with open(base + ".html", "w", encoding="utf-8") as f:
                f.write(self.page.content())
        except Exception as e:
            print(f"(dump failed: {e})", end=" ")

    # ---------- results ----------
    def results(self):
        rows = []
        for c in self.cases.values():
            row = {k: v for k, v in c.items() if k != "note"}
            if row["status"] == "NOT RUN" and self.stopped:
                row["status"] = "BLOCKED"
                row["actual"] = "Not executed - an earlier test case failed"
            rows.append(row)
        return rows

    def failed_ids(self):
        return [c["id"] for c in self.cases.values() if c["status"] == "FAILED"]


def read_progress(page):
    """Number in the progress circle next to 'Welcome, <name>' (None if not shown)."""
    return page.evaluate("""() => {
        const pct = [...document.querySelectorAll('span')].find(s => s.textContent.trim() === '%'
                     && s.previousElementSibling && /^\\d+$/.test(s.previousElementSibling.textContent.trim()));
        return pct ? parseInt(pct.previousElementSibling.textContent.trim()) : null;
    }""")


def short_error(e):
    text = str(e).replace("playwright._impl._errors.", "")
    text = text.split("Call log:")[0].split("=========")[0]
    return re.sub(r"\s+", " ", f"{type(e).__name__}: {text}").strip()[:400]
