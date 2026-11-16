# ============================================================
# REGRESSION TEST CASES
# Run all:        pytest tests/regression.py
# Run one:        pytest tests/regression.py -k test_01_onboarding
# Create 3 users: pytest tests/regression.py --users 3
#
# Add the next test case at the bottom as:  def test_02_<name>(page, steps):
# Wrap each part in  `with steps("name"):`  to see progress in the terminal.
# ============================================================
from pages.admin_agent_page import AdminAgentPage
from pages.admin_login_page import AdminLoginPage
from pages.agent_tools_page import AgentToolsPage
from pages.payment_page import PaymentPage
from pages.roa_application_page import RoaApplicationPage
from pages.roa_email_page import RoaEmailPage
from pages.sign_ica_page import SignIcaPage
from pages.signup_page import SignUpPage
from pages.tax_information_page import TaxInformationPage
from pages.transfer_license_page import TransferLicensePage


# ------------------------------------------------------------
# Test case 1: full agent onboarding (staging)
#   Part 1 - agent side:  sign up ... transfer license
#   Part 2 - admin side:  transfer now -> onboard agent -> status Active
# ------------------------------------------------------------
def test_01_onboarding(page, steps):
    # ---------- Part 1: agent onboarding ----------
    with steps("Sign up"):
        user = SignUpPage(page).create_new_user()
        steps.user = user                       # saved to created_users.csv
    with steps("ROA application"):
        RoaApplicationPage(page).complete(user)
    with steps("Tax information"):
        TaxInformationPage(page).complete(user)
    with steps("Sign ICA"):
        SignIcaPage(page).complete(user)
    with steps("Agent tools"):
        AgentToolsPage(page).complete()
    with steps("Payment"):
        PaymentPage(page).complete(user)
    with steps("ROA email"):
        RoaEmailPage(page).complete(user)
    with steps("Transfer license"):
        TransferLicensePage(page).complete()

    # ---------- Part 2: admin approves the same agent ----------
    with steps("Admin login"):
        AdminLoginPage(page).login()
    with steps("Admin approve -> Active"):
        AdminAgentPage(page).complete(user)
