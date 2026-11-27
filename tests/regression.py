# ============================================================
# REGRESSION TEST CASES (main test cases only)
# Run all:        pytest tests/regression.py
# Run one:        pytest tests/regression.py -k test_01_onboarding_without_sponsor_and_team
# Create 3 users: pytest tests/regression.py --users 3
#
# The sub test cases (TC_AO_001 ... TC_AO_053) of each main test case are in flows/.
# Results (PASSED / FAILED / BLOCKED / SKIPPED) -> dashboard + reports/testcase_results.csv
# ============================================================
import pytest

from flows import onboarding_multi_state, onboarding_without_sponsor_and_team


# Test case 1: Onboarding without Sponsor and Team
@pytest.mark.title("Onboarding without Sponsor and Team")
@pytest.mark.testcases("agent_onboarding_happy_flow.csv")
def test_01_onboarding_without_sponsor_and_team(page, steps, tc):
    onboarding_without_sponsor_and_team.run(page, steps, tc)


# Test case 2: Agent onboarding (happy flow without tagged sponsor & Team) - licensed in Alabama + Alaska
@pytest.mark.title("Agent onboarding (happy flow without tagged sponsor & Team)")
@pytest.mark.testcases("agent_onboarding_multi_state.csv")
def test_02_onboarding_multi_state_without_sponsor_and_team(page, steps, tc):
    onboarding_multi_state.run(page, steps, tc)
