# ============================================================
# TEST CASE 1 - Onboarding without Sponsor and Team (happy flow)
#   License: Yes (newly licensed, no license number yet) | Sponsor: No | Team: No
#
# All sub test cases of the sheet test_cases/agent_onboarding_happy_flow.csv:
#   every  `with tc("TC_AO_0xx"):`  block = one row of the sheet,
#   every  tc.step(...) / tc.see(...) / tc.check(...)  = one sub-case on the dashboard.
# Called from tests/regression.py -> test_01_onboarding_without_sponsor_and_team
# ============================================================
import re

from dummy_data import ADDRESS, BOARDS, EMERGENCY_CONTACT, NEW_LICENSE, PREFERRED_NAME, PROFESSIONAL, new_user
from flows.common import (agent_tools, check_app_store_links, create_account, pay_and_checkout,
                          roa_continue_to_tax, roa_email, roa_formal_to_success, roa_personal_details,
                          sign_ica, tax_information)
from pages.roa_application_page import RoaApplicationPage
from pages.transfer_license_page import TransferLicensePage


def run(page, steps, tc):
    """Run every stage of the onboarding with a new user, then fail if any test case failed."""
    user = new_user()
    steps.user = user                              # saved to created_users.csv
    print("User:", user["full_name"], "|", user["email"], "|", user["phone_number"])

    with steps("Create an Account"):
        create_account(page, tc, user)
    with steps("ROA Application"):
        roa_application(page, tc, user)
    with steps("Tax Information"):
        tax_information(page, tc, user)
    with steps("Sign Your ICA"):
        sign_ica(page, tc, user)
    with steps("Customize Agent Tools"):
        agent_tools(page, tc)
    with steps("Pay & Checkout"):
        pay_and_checkout(page, tc, user)
    with steps("Setup Your ROA Email"):
        roa_email(page, tc, user)
    with steps("Transfer License"):
        transfer_license(page, tc, user)

    failed = tc.failed_ids()
    assert not failed, f"{len(failed)} test case(s) failed: {', '.join(failed)}"


# ============================================================
# Stage 2 - ROA Application
# ============================================================
def roa_application(page, tc, user):
    roa = RoaApplicationPage(page)

    roa_personal_details(page, tc, user, roa)

    with tc("TC_AO_015"):
        with tc.step("Select 'I am a newly licensed agent (I do not have my license number)'"):
            page.wait_for_timeout(1000)
            roa.choose_radio("I am a newly licensed agent (I do not have my license number)")
        tc.see("Expected License Issuance Date")
        with tc.step("Pick Expected License Issuance Date, click 'Next'"):
            issue_date = roa.newly_licensed_without_number()
        tc.on_page("/new-agent-license-info", "'Tell us about your upcoming license' page opens")
        tc.see("Tell us about your upcoming license")
        tc.progress(30)
        tc.note(f"Expected License Issuance Date: {issue_date}")

    with tc("TC_AO_016"):
        with tc.step("Wait for the upcoming license form to load"):
            page.wait_for_function("() => document.querySelector(\"input[placeholder='Select Date']\")?.value",
                                   timeout=10_000)
        shown = roa.issue_date_box().input_value()
        tc.check(shown == issue_date, f"Estimated Date prefilled {issue_date}", f"shows '{shown}'")
        with tc.step(f"Select State '{NEW_LICENSE['state']}', Type '{NEW_LICENSE['type']}', click 'Next'"):
            roa.upcoming_license()
        tc.on_page("/real-estate-boards", "Real Estate Boards page opens")
        tc.progress(40)

    with tc("TC_AO_017"):
        state = NEW_LICENSE["state"]
        tc.see(f"Which Real Estate Board(s) are you a member of in {state}?",
               f"Which MLS(s) are you a member of in {state}?",
               re.compile(r"Can.t find your", re.I), "How to Verify Your MLS")

    with tc("TC_AO_018"):
        with tc.step(f"Select Board '{BOARDS['board']}' and MLS '{BOARDS['mls']}'"):
            roa.select_boards()
        tc.see(BOARDS["board"], BOARDS["mls"])
        with tc.step("Click 'Next'"):
            roa.click_next()
        tc.on_page("/formal-actions", "Formal Actions page opens")
        tc.progress(45)

    roa_formal_to_success(page, tc, user, roa)

    with tc("TC_AO_026"):
        with tc.step("Click 'View/Edit Your Responses'"):
            roa.click(roa.button("View/Edit Your Responses"))
        tc.see("Review your Application Responses")
        tc.see(PREFERRED_NAME, user["first_name"], user["last_name"], ADDRESS["line1"], ADDRESS["line2"],
               EMERGENCY_CONTACT["name"], EMERGENCY_CONTACT["email"],
               "I am a newly licensed agent (I do not have my license number)", issue_date.replace("/", "-"),
               NEW_LICENSE["type"], BOARDS["board"], BOARDS["mls"], PROFESSIONAL["nrds_id"],
               PROFESSIONAL["brokerage"], "Not Part of a Team")

    roa_continue_to_tax(tc, roa)


# ============================================================
# Stage 8 - Transfer License
# ============================================================
def transfer_license(page, tc, user):
    transfer = TransferLicensePage(page)
    state = NEW_LICENSE["state"]

    with tc("TC_AO_050"):
        tc.on_page("/transfer-license", "Transfer License page opens")
        tc.see("Congrats", user["full_name"], "Completed Your Application", "Transfer Your License to Realty of America",
               "Your License Transfers", state, "Newly Licensed", f"{state} License Transfer Instructions",
               "Upload Documents", "download our mobile app")

    with tc("TC_AO_051"):
        with tc.step(f"Click '{state} License Transfer Instructions'"):
            opened = transfer.click_and_catch(transfer.card_action(f"{state} License Transfer Instructions"))
        if opened.get("page"):
            opened["page"].wait_for_load_state("domcontentloaded")
            tc.check(True, "Instructions open in a new tab")
            tc.note(f"Instructions: {opened['page'].url[:120]}")
            opened["page"].close()
        elif opened.get("download"):
            tc.check(True, "Instructions download")
            tc.note(f"Instructions downloaded: {opened['download'].suggested_filename}")
        else:
            dialog = page.get_by_role("dialog")
            if tc.see_element(dialog, "instructions popup"):
                tc.see(state, root=dialog)
                page.keyboard.press("Escape")
                dialog.wait_for(state="hidden", timeout=10_000)

    with tc("TC_AO_052"):
        with tc.step("Click 'Upload Documents' and choose license_document.pdf"):
            name = transfer.upload_document()
        tc.see(name, "100% uploaded", timeout=10_000)

    with tc("TC_AO_053"):
        check_app_store_links(tc, transfer)
