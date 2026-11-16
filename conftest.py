# ============================================================
# Browser setup used by every test (the `page` you get in tests)
# ============================================================
import csv
import datetime as dt
import os
import time
from contextlib import contextmanager

import pytest

import config

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
            print(f"{title} ... FAILED ({time.time() - start:.0f}s)")
            raise
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
        failed_step = steps.failed_step if steps else None
        user = steps.user if steps else None
        if user:
            save_user(steps, report.outcome)
        RESULTS.append((label, report.outcome, report.duration, failed_step, user))


def pytest_terminal_summary(terminalreporter):
    if not RESULTS:
        return
    terminalreporter.section("TEST CASE RESULTS")
    for label, outcome, seconds, failed_step, user in RESULTS:
        status = "PASSED" if outcome == "passed" else "FAILED"
        if failed_step:
            status += f" at '{failed_step}'"
        minutes, secs = divmod(int(seconds), 60)
        line = f"{label} {'.' * max(3, 45 - len(label))} {status}  ({minutes}m {secs}s)"
        terminalreporter.write_line(line, green=(outcome == "passed"), red=(outcome != "passed"), bold=True)
        if user:
            terminalreporter.write_line(f"      user: {user['full_name']} | {user['email']} | {user['phone_number']}")
    passed = sum(1 for r in RESULTS if r[1] == "passed")
    terminalreporter.write_line(f"\nTotal: {len(RESULTS)}   Passed: {passed}   Failed: {len(RESULTS) - passed}", bold=True)
