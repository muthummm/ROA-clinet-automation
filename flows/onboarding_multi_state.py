# ============================================================
# TEST CASE 2 - Agent onboarding (happy flow without tagged sponsor & Team)
#   License: Yes - newly licensed WITH license number, licensed in 2 states (Alabama + Alaska)
#   Sponsor: No | Team: No
#
# All sub test cases of the sheet test_cases/agent_onboarding_multi_state.csv (TC_AO_001 ... TC_AO_057):
#   every  `with tc("TC_AO_0xx"):`  block = one row of the sheet,
#   every  tc.step(...) / tc.see(...) / tc.check(...)  = one sub-case on the dashboard.
# Stages that are the same as test case 1 come from flows/common.py
#   (shift=4: this sheet numbers those test cases 4 higher than sheet 1).
# Called from tests/regression.py -> test_02_...
# ============================================================
import datetime as dt
import re

from dummy_data import (ADDRESS, EMERGENCY_CONTACT, MULTI_STATE_BOARDS, MULTI_STATE_LICENSES, PREFERRED_NAME,
                        PROFESSIONAL, new_user)
from flows.common import (agent_tools, check_app_store_links, create_account, pay_and_checkout,
                          roa_continue_to_tax, roa_email, roa_formal_to_success, roa_personal_details,
                          sign_ica, tax_information)
from pages.roa_application_page import RoaApplicationPage
from pages.transfer_license_page import TransferLicensePage

SHIFT = 4                                         # TC numbers after the license pages are 4 higher than sheet 1
STATES = [lic["state"] for lic in MULTI_STATE_LICENSES]


def run(page, steps, tc):
    """Run every stage of the onboarding with a new user, then fail if any test case failed."""
    user = new_user()
    # a license number can be registered only once -> sheet number + this user's phone suffix (new every run)
    user["licenses"] = [{**lic, "number": f"{lic['number']}-{user['phone_number'][-4:]}"}
                        for lic in MULTI_STATE_LICENSES]
    steps.user = user                              # saved to created_users.csv
    print("User:", user["full_name"], "|", user["email"], "|", user["phone_number"])

    with steps("Create an Account"):
        create_account(page, tc, user)
    with steps("ROA Application"):
        roa_application(page, tc, user)
    with steps("Tax Information"):
        tax_information(page, tc, user, shift=SHIFT)
    with steps("Sign Your ICA"):
        sign_ica(page, tc, user, shift=SHIFT)
    with steps("Customize Agent Tools"):
        agent_tools(page, tc, shift=SHIFT)
    with steps("Pay & Checkout"):
        pay_and_checkout(page, tc, user, shift=SHIFT)
    with steps("Setup Your ROA Email"):
        roa_email(page, tc, user, shift=SHIFT)
    with steps("Transfer License"):
        transfer_license(page, tc, user)

    failed = tc.failed_ids()
    assert not failed, f"{len(failed)} test case(s) failed: {', '.join(failed)}"


def date_from_today(days):
    return (dt.date.today() + dt.timedelta(days=days)).strftime("%m/%d/%Y")


# ============================================================
# Stage 2 - ROA Application
# ============================================================
def roa_application(page, tc, user):
    roa = RoaApplicationPage(page)
    roa_personal_details(page, tc, user, roa)                    # TC_AO_008 ... TC_AO_014

    with tc("TC_AO_015"):
        with tc.step("Select 'I am a newly licensed agent (I have my license number)'"):
            page.wait_for_timeout(1000)
            roa.choose_radio("I am a newly licensed agent (I have my license number)")
        page.wait_for_timeout(500)
        tc.check(not page.get_by_text("Expected License Issuance Date").is_visible(),
                 "No issuance date field for this option", "'Expected License Issuance Date' is shown")
        with tc.step("Click 'Next'"):
            roa.answer_radio("/license-status", "I am a newly licensed agent (I have my license number)")
        tc.on_page("/licensed-in-multiple-states", "'Are you licensed in multiple states?' page opens")
        tc.progress(30)

    with tc("TC_AO_016"):
        tc.see("Are you licensed in multiple states?", "more than one state", "Yes", "No", "Back", "Next")

    with tc("TC_AO_017"):
        with tc.step("Select 'Yes', click 'Next'"):
            roa.answer_radio("/licensed-in-multiple-states", "Yes")
        tc.on_page("/licensed-details", "Real Estate License Details page opens")
        tc.progress(35)

    with tc("TC_AO_018"):
        tc.see("Real Estate License Details", "Primary State", "What type of license is it?", "License Number",
               "Expiration Date", "When do you plan to transfer this license?", "Additional Licenses",
               "Add Additional License")
        for i, part in enumerate(["Primary", "Additional"]):
            tc.see_element(roa.input(f"licenses.{i}.license_no"), f"{part} License Number field")
        dates = page.locator("input[placeholder='MM/DD/YYYY']").count()
        tc.check(dates == 4, "Expiration + transfer date for both licenses (4 date fields)", f"{dates} date fields")

    with tc("TC_AO_019"):
        text = "; ".join(f"{lic['state']} {lic['type']} #{lic['number']}" for lic in user["licenses"])
        with tc.step(f"Enter licenses ({text}) with expiration + transfer dates, click 'Next'"):
            roa.fill_and_next(lambda: roa.fill_license_details(user["licenses"]))
        tc.on_page("/real-estate-boards", "Real Estate Boards page opens")
        tc.progress(40)

    with tc("TC_AO_020"):
        for state in STATES:
            tc.see(f"Which Real Estate Board(s) are you a member of in {state}?",
                   f"Which MLS(s) are you a member of in {state}?",
                   re.compile(rf"Can.t find your Board in {state}"), re.compile(rf"Can.t find your MLS\(s\) in {state}"))
        tc.see("How to Verify Your MLS")
        boxes = page.locator("input[role='combobox']").count()
        tc.check(boxes == 2 * len(STATES), f"Board + MLS dropdown for each state ({2 * len(STATES)})",
                 f"{boxes} dropdowns")

    with tc("TC_AO_021"):
        alaska = MULTI_STATE_BOARDS["Alaska"]
        with tc.step(f"Select Alaska Board '{alaska['board']}' (not active with ROA)"):
            page.wait_for_timeout(1500)                           # the page loads its saved data first
            roa.select_board_option(2, alaska["board"])
        with tc.step(f"Select Alaska MLS '{alaska['mls']}' (not active with ROA)"):
            roa.select_board_option(3, alaska["mls"])
        tc.see(alaska["board"], alaska["mls"], "is not currently active with ROA", "You can continue signing up")
        warnings = page.get_by_text("is not currently active with ROA").count()
        tc.check(warnings >= 2, "Warning under the Board and under the MLS", f"{warnings} warning(s)")
        tc.see(re.compile("ROA Support", re.I))

    with tc("TC_AO_022"):
        alabama = MULTI_STATE_BOARDS["Alabama"]
        with tc.step(f"Select Alabama Board '{alabama['board']}' and MLS '{alabama['mls']}'"):
            roa.select_board_option(0, alabama["board"])
            roa.select_board_option(1, alabama["mls"])
        tc.see(alabama["board"], alabama["mls"], alaska["board"], alaska["mls"])
        with tc.step("Click 'Next'"):
            roa.click_next()
        tc.on_page("/formal-actions", "Formal Actions page opens")
        tc.progress(45)

    roa_formal_to_success(page, tc, user, roa, shift=SHIFT)      # TC_AO_023 ... TC_AO_029

    with tc("TC_AO_030"):
        with tc.step("Click 'View/Edit Your Responses'"):
            roa.click(roa.button("View/Edit Your Responses"))
        tc.see("Review your Application Responses")
        answers = [PREFERRED_NAME, user["first_name"], user["last_name"], ADDRESS["line1"], ADDRESS["line2"],
                   EMERGENCY_CONTACT["name"], EMERGENCY_CONTACT["email"],
                   "I am a newly licensed agent (I have my license number)", PROFESSIONAL["nrds_id"],
                   PROFESSIONAL["brokerage"], "Not Part of a Team"]
        for lic in user["licenses"]:
            answers += [lic["state"], lic["number"]]
        for state in STATES:
            answers += [MULTI_STATE_BOARDS[state]["board"], MULTI_STATE_BOARDS[state]["mls"]]
        tc.see(*answers)

    roa_continue_to_tax(tc, roa, shift=SHIFT)                    # TC_AO_031


# ============================================================
# Stage 8 - Transfer License (one card per state)
# ============================================================
def transfer_license(page, tc, user):
    transfer = TransferLicensePage(page)

    with tc("TC_AO_054"):
        tc.on_page("/transfer-license", "Transfer License page opens")
        tc.see("Congrats", user["full_name"], "Completed Your Application", "Transfer Your License to Realty of America",
               "Your License Transfers", "download our mobile app")
        for lic in user["licenses"]:
            state = lic["state"]
            card = transfer.license_card(state)
            if not tc.see_element(card, f"{state} license card"):
                continue
            tc.see(state, lic["number"], "Planned Transfer Date", f"{state} License Transfer Instructions",
                   "Upload Documents", root=card)
            planned = date_from_today(lic["transfer_days_from_today"])
            card_text = card.inner_text()
            tc.check(planned in card_text or planned.replace("/", "-") in card_text,
                     f"{state} card shows planned transfer date {planned}",
                     re.sub(r"\s+", " ", card_text)[:120])

    with tc("TC_AO_055"):
        for state in STATES:
            button = transfer.card_action(f"{state} License Transfer Instructions", state)
            if not tc.check(button.is_enabled(), f"'{state} License Transfer Instructions' is clickable",
                            "button is disabled"):
                continue
            with tc.step(f"Click '{state} License Transfer Instructions'"):
                opened = transfer.click_and_catch(button)
            if opened.get("page"):
                opened["page"].wait_for_load_state("domcontentloaded")
                tc.check(True, f"{state} instructions open in a new tab")
                tc.note(f"{state}: {opened['page'].url[:110]}")
                opened["page"].close()
            elif opened.get("download"):
                tc.check(True, f"{state} instructions download")
            else:
                dialog = page.get_by_role("dialog")
                if tc.see_element(dialog, f"{state} instructions popup"):
                    page.keyboard.press("Escape")
                    dialog.wait_for(state="hidden", timeout=10_000)

    with tc("TC_AO_056"):
        for state in STATES:
            with tc.step(f"Click 'Upload Documents' on the {state} card and choose license_document.pdf"):
                name = transfer.upload_document(state=state)
            tc.see(name, "100% uploaded", root=transfer.license_card(state))

    with tc("TC_AO_057"):
        check_app_store_links(tc, transfer)
