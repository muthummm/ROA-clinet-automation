# ============================================================
# Browser setup used by every test (the `page` you get in tests)
# ============================================================
import csv
import datetime as dt
import glob
import os
import pathlib
import shutil
import subprocess
import time
import webbrowser
from contextlib import contextmanager

import pytest
from slugify import slugify          # comes with pytest-playwright (same names it uses for screenshot folders)

import config
import dashboard

USERS_FILE = os.path.join(os.path.dirname(__file__), "created_users.csv")


# ============================================================
# --users N  ->  run each test N times (= create N users)
#   pytest --users 3
# ============================================================
def pytest_addoption(parser):
    parser.addoption("--users", type=int, default=1, help="how many users to create (runs each test N times)")


def pytest_generate_tests(metafunc):
    count = metafunc.config.getoption("users")
    if count > 1:
        metafunc.fixturenames.append("run_no")
        metafunc.parametrize("run_no", range(1, count + 1), indirect=True,
                             ids=[f"user{i}" for i in range(1, count + 1)])


@pytest.fixture
def run_no(request):
    return request.param


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {**browser_type_launch_args, "headless": config.HEADLESS}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1366, "height": 900}}


@pytest.fixture
def page(page):
    page.set_default_timeout(config.DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(config.NAV_TIMEOUT)
    yield page


# ============================================================
# steps - show progress of a test in the terminal
#   with steps("Sign up"):
#       ...
# prints:  [STEP 1] Sign up ... done (25s)
# ============================================================
class Steps:
    def __init__(self):
        self.number = 0
        self.failed_step = None
        self.user = None          # set steps.user = user -> saved to created_users.csv
        self.records = []         # [{name, seconds, status}] -> shown on the dashboard

    @contextmanager
    def __call__(self, name):
        self.number += 1
        title = f"[STEP {self.number}] {name}"
        print(f"\n{title} ...")
        start = time.time()
        try:
            yield
        except BaseException:
            self.failed_step = name
            self.records.append({"name": name, "seconds": round(time.time() - start), "status": "failed"})
            print(f"{title} ... FAILED ({time.time() - start:.0f}s)")
            raise
        self.records.append({"name": name, "seconds": round(time.time() - start), "status": "done"})
        print(f"{title} ... done ({time.time() - start:.0f}s)")


@pytest.fixture
def steps(request):
    request.node.steps = Steps()
    return request.node.steps


def save_user(steps, outcome):
    """Add one row to created_users.csv for every user the test created."""
    user = steps.user
    new_file = not os.path.exists(USERS_FILE)
    with open(USERS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["Date", "Name", "Email", "Phone", "Result", "Failed step"])
        writer.writerow([dt.datetime.now().strftime("%Y-%m-%d %H:%M"), user["full_name"], user["email"],
                         user["phone_number"], outcome.upper(), steps.failed_step or ""])


# ============================================================
# Result summary at the end of the run, e.g.
#   Test case 1 - Onboarding ............ PASSED  (3m 30s)
# ============================================================
RESULTS = []


def test_case_label(function_name):
    """test_01_onboarding -> 'Test case 1 - Onboarding'"""
    name = function_name.removeprefix("test_")
    number, _, rest = name.partition("_")
    if number.isdigit():
        return f"Test case {int(number)} - {rest.replace('_', ' ').title()}"
    return name.replace("_", " ").title()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # record the test result (or a setup error, e.g. browser did not start)
    if report.when == "call" or (report.when == "setup" and not report.passed):
        label = test_case_label(item.originalname or item.name)
        params = getattr(item, "callspec", None)
        if params and "run_no" in params.params:
            label += f" (user {params.params['run_no']})"
        steps = getattr(item, "steps", None)
        if steps and steps.user:
            save_user(steps, report.outcome)
        error = ""
        if call.excinfo is not None:
            error = call.excinfo.exconly().replace("playwright._impl._errors.", "")[:1500]
        RESULTS.append({
            "date": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "test": label,
            "nodeid": item.nodeid,
            "outcome": report.outcome,
            "duration": round(report.duration),
            "failed_step": steps.failed_step if steps else None,
            "user": steps.user if steps else None,
            "steps": steps.records if steps else [],
            "error": error,
        })


def pytest_terminal_summary(terminalreporter):
    if not RESULTS:
        return
    terminalreporter.section("TEST CASE RESULTS")
    for r in RESULTS:
        status = "PASSED" if r["outcome"] == "passed" else "FAILED"
        if r["failed_step"]:
            status += f" at '{r['failed_step']}'"
        minutes, secs = divmod(r["duration"], 60)
        line = f"{r['test']} {'.' * max(3, 45 - len(r['test']))} {status}  ({minutes}m {secs}s)"
        terminalreporter.write_line(line, green=(r["outcome"] == "passed"), red=(r["outcome"] != "passed"), bold=True)
        if r["user"]:
            u = r["user"]
            terminalreporter.write_line(f"      user: {u['full_name']} | {u['email']} | {u['phone_number']}")
    passed = sum(1 for r in RESULTS if r["outcome"] == "passed")
    terminalreporter.write_line(f"\nTotal: {len(RESULTS)}   Passed: {passed}   Failed: {len(RESULTS) - passed}", bold=True)

    # ---------- dashboard ----------
    try:
        path = update_dashboard(terminalreporter.config)
        terminalreporter.write_line(f"\nDashboard: {path}", bold=True)
        if config.OPEN_DASHBOARD and not config.HEADLESS:
            open_dashboard(path)
            terminalreporter.write_line("Dashboard opened in a new browser window (close it yourself when done).")
    except Exception as e:                       # the dashboard must never break the test run
        terminalreporter.write_line(f"Dashboard not created: {e}", yellow=True)


def open_dashboard(path):
    """Open the dashboard in its own Chromium window and close it again after 5 seconds.
    (The file stays in reports/dashboard.html - open it again any time.)"""
    url = pathlib.Path(path).as_uri()
    browsers = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    chrome = sorted(glob.glob(os.path.join(browsers, "chromium-*", "chrome-win*", "chrome.exe")))
    if not chrome:
        webbrowser.open(url)                     # no Playwright Chromium found -> use the normal browser
        return
    profile = os.path.join(os.path.dirname(path), ".dashboard-browser")
    window = subprocess.Popen(
        [chrome[-1], f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
         "--new-window", "--start-maximized", url],
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
    )
    time.sleep(5)                                # show the dashboard for 5 seconds
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(window.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def update_dashboard(pytest_config):
    """Copy failure screenshots, add this run to reports/history.json, rebuild reports/dashboard.html."""
    reports = pytest_config.getoption("output") or "reports"
    os.makedirs(os.path.join(reports, "screenshots"), exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, r in enumerate(RESULTS, 1):
        shot = os.path.join(reports, slugify(r["nodeid"]), "test-failed-1.png")
        if r["outcome"] != "passed" and os.path.exists(shot):
            name = f"screenshots/{stamp}_{i}.png"
            shutil.copy(shot, os.path.join(reports, name))
            r["screenshot"] = name
    history_file = os.path.join(reports, "history.json")
    history = dashboard.load_history(history_file) + [{k: v for k, v in r.items() if k != "nodeid"} for r in RESULTS]
    dashboard.save_history(history_file, history)
    return os.path.abspath(dashboard.build_dashboard(history, history[-len(RESULTS):],
                                                     os.path.join(reports, "dashboard.html")))
