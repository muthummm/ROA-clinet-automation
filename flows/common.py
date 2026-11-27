# ============================================================
# STAGES SHARED BY THE ONBOARDING TEST CASES
# Each function runs the sub test cases of one stage. The TC numbers are the ones of
# test case 1; shift=4 means "this sheet numbers the same test cases 4 higher" (test case 2).
# ============================================================
import datetime as dt
import re

from config import OTP
from dummy_data import ADDRESS, EMERGENCY_CONTACT, PREFERRED_NAME, PROFESSIONAL
from pages.agent_tools_page import AgentToolsPage
from pages.payment_page import PaymentPage
from pages.roa_email_page import RoaEmailPage
from pages.sign_ica_page import SignIcaPage
from pages.signup_page import SignUpPage
from pages.tax_information_page import TaxInformationPage

STAGES = ["Create an Account", "ROA Application", "Tax Information", "Sign Your ICA",
          "Customize Agent Tools", "Pay & Checkout", "Setup Your ROA Email", "Transfer License"]


def tid(number, shift=0):
    """tid(28, 4) -> 'TC_AO_032'"""
    return f"TC_AO_{number + shift:03d}"


# ============================================================
# Stage 1 - Create an Account
# ============================================================
def create_account(page, tc, user, shift=0):
    signup = SignUpPage(page)

    with tc(tid(1, shift)):
        with tc.step("Open the sign-up page"):
            signup.open_sign_up()
        tc.see("Step: 1/2", "Create an Account", "Get started", "Already have an account?", "Sign LOI", "EN", "ES")
        tc.see_element(signup.input("email"), "Email field")

    with tc(tid(2, shift)):
        with tc.step(f"Enter email {user['email']} and click 'Get started'"):
            signup.submit_email(user["email"])
        tc.see("Verify your email", user["email"], "6-digit code", "expires in 5 minutes", "Change email",
               "Cancel", "Continue", re.compile("Resend", re.I))
        boxes = signup.otp_boxes().count()
        tc.check(boxes == 6, "6 OTP boxes shown", f"{boxes} boxes")

    tc.skip(tid(3, shift), f"Not automated - staging accepts the fixed OTP {OTP}, the inbox is not checked")

    with tc(tid(4, shift)):
        with tc.step(f"Enter OTP {OTP} and click 'Continue'"):
            signup.verify_otp()
        tc.see("Step: 2/2", "Verified")
        email = signup.input("email").input_value()
        tc.check(email == user["email"], "Email field prefilled with the verified email", f"shows '{email}'")

    with tc(tid(5, shift)):
        for name, label in [("first_name", "First Name"), ("last_name", "Last Name"), ("email", "Email"),
                            ("phone_number", "Phone Number"), ("password", "Password"),
                            ("confirm_password", "Confirm Password")]:
            tc.see_element(signup.input(name), f"{label} field")
        tc.see("+1", "Primary State", "Get started", "Login")

    with tc(tid(6, shift)):
        with tc.step("Fill First Name, Last Name, Phone, Primary State, Password, Confirm Password"):
            signup.fill_account_details(user)
        with tc.step("Click 'Get started' -> onboarding dashboard opens"):
            signup.create_account()
        tc.see(user["full_name"])
        tc.progress(0)

    with tc(tid(7, shift)):
        tc.see(*STAGES, "Logout", "EN", "ES")
        order = page.evaluate("""stages => { const t = document.body.innerText;
                                 return stages.map(s => t.indexOf(s)); }""", STAGES)
        tc.check(order == sorted(order) and -1 not in order, "8 stages listed in the right order", f"{order}")


# ============================================================
# Stage 3 - Tax Information
# ============================================================
def tax_information(page, tc, user, shift=0):
    tax = TaxInformationPage(page)

    with tc(tid(28, shift)):
        with tc.step("Click 'Next' on the intro page -> Substitute W-9 form"):
            tax.open_w9_form()
        tc.see("How Will You Receive Payment from Realty of America", "Individual", "Entity",
               "Taxpayer or Business Name", "Disregarded Entity Name", "SSN", "EIN", "Tax Classification",
               "State", "City", "Zip Code", "Back", "Next")

    with tc(tid(29, shift)):
        with tc.step("Select Individual, enter name and SSN, pick Tax Classification, address, State, City, Zip"):
            page.wait_for_timeout(1500)                    # the form loads its saved data first
            tax.fill_w9(user)
        ssn = tax.ssn_box().input_value()
        tc.check("*" in ssn or "•" in ssn, "SSN is masked", f"shows '{ssn}'")
        filled = [True]

        def fill_again_if_reset():
            if filled.pop() if filled else False:
                return                                     # first try: already filled above
            tax.fill_w9(user)
        with tc.step("Click 'Next'"):
            tax.fill_and_next(fill_again_if_reset)
        tc.on_page("/tax-information/step-3", "Tax Information success page opens")
        tc.progress(75)

    with tc(tid(30, shift)):
        tc.see("Congrats", user["full_name"], "Submitted Your Tax Information", "View/Edit Your Responses",
               "Continue: Sign Your ICA")

    with tc(tid(31, shift)):
        with tc.step("Click 'Continue: Sign Your ICA'"):
            tax.continue_to_ica()
        tc.see("Independent Contractor Agreement")


# ============================================================
# Stage 4 - Sign Your ICA
# ============================================================
def sign_ica(page, tc, user, shift=0):
    ica = SignIcaPage(page)

    with tc(tid(32, shift)):
        tc.see("Independent Contractor Agreement", "ROA Independent Contractor Agreement", "View",
               "Continue to E-Sign ICA")
        tc.progress(75)

    with tc(tid(33, shift)):
        with tc.step("Click 'View' on the ICA card"):
            ica.click(ica.button("View").first)
        check_ica_preview(tc, page, ica, download=False)

    with tc(tid(34, shift)):
        with tc.step("Click 'Continue to E-Sign ICA' -> Dropbox Sign window loads"):
            ica.open_esign()
        tc.see(re.compile(r"\d+ required fields"), "Get started", root=ica.esign())
        tc.see_element(ica.esign().locator("[data-qa-ref='page-0']"), "ICA document in the e-sign window")

    with tc(tid(35, shift)):
        with tc.step("Close 'not legally binding' popup, click 'Get started'"):
            ica.start_signing()
        tc.see(re.compile(r"\d+ required fields? left"), root=ica.esign())
        with tc.step("Click the first required initials field"):
            ica.open_first_initials()
        tc.see("Draw", "Type", "Upload", "Insert", root=ica.esign())
        with tc.step(f"Type initials '{user['initials']}' and insert them in all fields"):
            ica.insert_initials_everywhere(user)

    with tc(tid(36, shift)):
        with tc.step("Fill the remaining mandatory initials / signature fields"):
            ica.fill_mandatory_fields(user)
        left = ica.fields_left()
        text = left.inner_text().strip() if left.count() and left.is_visible() else "0"
        tc.check(text.startswith("0"), "Required fields left = 0", text)

    with tc(tid(37, shift)):
        with tc.step("Click 'Continue' and 'I agree'"):
            ica.submit()
        tc.see("Thanks for submitting your document!", root=ica.esign())

    with tc(tid(38, shift)):
        with tc.step("Click 'Close' in the e-sign window"):
            result = ica.close_after_submit()
        if tc.check(result == "success", "ICA success page shown", "app went straight to Agent Tools"):
            tc.see("Congrats", user["full_name"], "Signed your ICA", "Digitally signed on",
                   "View/Download ICA", "Continue: Customize Agent Tools")
            today = dt.date.today()
            tc.check(page.get_by_text(re.compile(rf"{today.strftime('%b')}\w*\.? 0?{today.day},? {today.year}|"
                                                 rf"{today.strftime('%m/%d/%Y')}")).count() > 0,
                     "'Digitally signed on' is today's date", "another date")
            tc.progress(80)

    with tc(tid(39, shift)):
        with tc.step("Click 'View/Download ICA'"):
            if "/customize-agent-tools" in page.url:
                raise AssertionError("ICA success page not shown - cannot view/download the signed ICA")
            ica.click(ica.button("View/Download ICA"))
        check_ica_preview(tc, page, ica, download=True)

    ica.continue_to_agent_tools()


def check_ica_preview(tc, page, ica, download):
    """'ICA Preview' popup: the document loads, Download gives a PDF, Close closes it."""
    preview = page.get_by_role("dialog")
    tc.see("ICA Preview", "Download", "Close", root=preview)
    # the document is shown either in a PDF viewer or an embedded PDF frame
    document = preview.locator("[class*='rpv-core__page-layer'], [class*='rpv-core__inner-page'], "
                               ".rpv-core__text-layer, canvas, iframe[src], embed[src], object[data]")
    tc.see_element(document, "ICA document in the preview", timeout=10_000)
    if download:
        with tc.step("Click 'Download'"):
            got = ica.click_and_catch(preview.locator("button", has_text=re.compile(r"^\s*Download\s*$")), 10_000)
        name = (got["download"].suggested_filename if got.get("download")
                else got["page"].url[:100] if got.get("page") else "")
        if tc.check(bool(name), "Signed ICA PDF downloads", "nothing downloaded"):
            tc.note(f"Signed ICA downloaded: {name}")
            if got.get("page"):
                got["page"].close()
    with tc.step("Close the preview"):
        ica.click(preview.locator("button", has_text=re.compile(r"^\s*Close\s*$")))
        preview.wait_for(state="hidden", timeout=10_000)


# ============================================================
# Stage 5 - Customize Agent Tools
# ============================================================
def agent_tools(page, tc, shift=0):
    tools = AgentToolsPage(page)

    with tc(tid(40, shift)):
        tc.on_page("/customize-agent-tools", "Agent Tools page opens")
        popup = tools.stay_connected_popup()
        tc.see("Stay Connected", "Agent Directory", "Founding Partner Network", "Learn More", "Skip for now",
               "Agree and Continue", root=popup)
        boxes = popup.locator("input[type='checkbox']")
        ticked = sum(1 for i in range(boxes.count()) if boxes.nth(i).is_checked())
        tc.check(ticked == 2, "Both consent checkboxes ticked by default", f"{ticked} of {boxes.count()} ticked")

    with tc(tid(41, shift)):
        with tc.step("Click 'Agree and Continue'"):
            tools.agree_and_continue()
        tc.see("Agent Tools To Level Up Your Business")

    with tc(tid(42, shift)):
        tc.see("Follow Up Boss", "Cloze", "You can only select any one CRM tool", "Okta", "Brokerage Engine",
               re.compile("skyslope", re.I), "Automatically included", "RealScout", "Add at No Additional Cost",
               "Microsoft 365", "$225", "Continue: Pay & Checkout")

    with tc(tid(43, shift)):
        with tc.step("Select no tool, click 'Continue: Pay & Checkout'"):
            tools.continue_to_payment()
        tc.progress(85)


# ============================================================
# Stage 6 - Pay & Checkout
# ============================================================
def pay_and_checkout(page, tc, user, shift=0):
    payment = PaymentPage(page)

    with tc(tid(44, shift)):
        with tc.step("Wait for the Stripe checkout (test mode) to load"):
            payment.wait_for_checkout()
        stripe = payment.stripe()
        tc.see("$199.00", "Card information", "Cardholder name", "Country or region", "Pay", root=stripe)
        email = stripe.locator("#email")
        shown = email.input_value() if email.count() else (user["email"] if stripe.get_by_text(user["email"]).count()
                                                           else "")
        tc.check(shown == user["email"], "Email prefilled with the account email", f"shows '{shown}'")

    with tc(tid(45, shift)):
        with tc.step("Enter test card 4242..., expiry, CVC, cardholder name, country"):
            payment.fill_card(user)
        with tc.step("Click 'Pay'"):
            payment.pay()
        with tc.step("Continue to 'Set Up Your Realty of America Email'"):
            payment.continue_to_roa_email()
        tc.progress(90)


# ============================================================
# Stage 7 - Setup Your ROA Email
# ============================================================
def roa_email(page, tc, user, shift=0):
    email = RoaEmailPage(page)

    with tc(tid(46, shift)):
        with tc.step("Wait for the ROA email page"):
            email.wait_for_email_page()
        tc.see("Suggested ROA Email Address", "Send code", "Next")
        tc.see_element(email.input("forwarding_email"), "Forwarding Email field")
        tc.check(email.next_button().is_disabled(), "'Next' is disabled", "'Next' is enabled")

    with tc(tid(47, shift)):
        with tc.step("Pick the first suggested ROA email"):
            email.choose_suggested_email()
        tc.see("This email address is available!", "@realtyofamerica.com")

    with tc(tid(48, shift)):
        with tc.step(f"Enter forwarding email {user['email']}, click 'Send code'"):
            email.send_code(user["email"])
        tc.see("Enter the OTP we sent to", re.compile("Resend", re.I))
        boxes = page.locator("input[aria-label='Please enter your pin code']").count()
        tc.check(boxes == 6, "6 OTP boxes shown", f"{boxes} boxes")

    with tc(tid(49, shift)):
        with tc.step(f"Enter OTP {OTP}"):
            email.verify_code()
        with tc.step("Tick acknowledgement, click 'Next' + confirm"):
            email.submit()
        tc.see("Congrats", user["full_name"], "Your ROA Email Setup is Complete", "Continue: Transfer License")
        tc.progress(95)
        with tc.step("Click 'Continue: Transfer License'"):
            email.continue_to_transfer_license()




def check_app_store_links(tc, transfer):
    for store, site in {"App Store": "apps.apple.com", "Google Play": "play.google.com"}.items():
        with tc.step(f"Click '{store}'"):
            opened = transfer.click_and_catch(transfer.store_link(store))
        new_tab = opened.get("page")
        if tc.check(new_tab is not None, f"'{store}' opens a new tab", "no new tab"):
            new_tab.wait_for_load_state("commit")
            tc.check(site in new_tab.url, f"'{store}' opens {site}", new_tab.url[:80])
            new_tab.close()


# ============================================================
# Stage 2 - ROA Application (parts that are the same for every test case)
# ============================================================
def roa_personal_details(page, tc, user, roa, shift=0):
    """Personal details, address, emergency contact, active license question, license status options."""
    with tc(tid(8, shift)):
        with tc.step("Wait for the personal details form to load"):
            roa.wait_for_prefilled_details()
        tc.see("Tell Us A Little More About Yourself", "Birthdate", "Next")
        tc.see_element(roa.input("preferred_name"), "Preferred Name field")
        first, last = roa.input("first_name").input_value(), roa.input("last_name").input_value()
        tc.check(first == user["first_name"], f"First Name prefilled '{user['first_name']}'", f"shows '{first}'")
        tc.check(last == user["last_name"], f"Last Name prefilled '{user['last_name']}'", f"shows '{last}'")
        phone = re.sub(r"\D", "", roa.input("phone_number").input_value())
        tc.check(phone.endswith(user["phone_number"]), "Phone Number prefilled", f"shows '{phone}'")
        tc.progress(0)

    with tc(tid(9, shift)):
        with tc.step(f"Enter Preferred Name '{PREFERRED_NAME}', pick Birthdate, click 'Next'"):
            roa.about_yourself(user)
        tc.on_page("/your-residential-address", "Residential Details page opens")
        tc.progress(5)

    with tc(tid(10, shift)):
        tc.see("Mailing Address", "Address Line 2", "State", "City", "Zip Code", "Select a state first", "Back", "Next")
        tc.see_element(roa.input("address_line_1"), "Address Line 1 field")
        city = roa.dropdown("City")
        tc.check(city.is_disabled() or page.get_by_text("Select a state first").count() > 0,
                 "City disabled until a State is picked", "City is enabled")

    with tc(tid(11, shift)):
        with tc.step(f"Enter address '{ADDRESS['line1']}, {ADDRESS['line2']}', pick State, City, Zip Code, "
                     "click 'Next'"):
            roa.residential_address()
        tc.on_page("/your-emergency-contact", "Emergency Contact page opens")
        tc.progress(10)

    with tc(tid(12, shift)):
        with tc.step(f"Enter emergency contact '{EMERGENCY_CONTACT['name']}', phone, relationship, email, "
                     "click 'Next'"):
            roa.emergency_contact()
        tc.on_page("/active-license", "Active license question page opens")
        tc.see("active real estate license")
        tc.progress(15)

    with tc(tid(13, shift)):
        with tc.step("Select 'Yes', click 'Next'"):
            roa.answer_radio("/active-license", "Yes")
        tc.on_page("/license-status", "License Status page opens")
        tc.see("Which of the following best describes your license status?")
        tc.progress(20)

    with tc(tid(14, shift)):
        tc.see("I hold an active license", "I am a newly licensed agent (I have my license number)",
               "I am a newly licensed agent (I do not have my license number)", "Back", "Next")


def roa_formal_to_success(page, tc, user, roa, shift=0):
    """Formal actions, professional experience, no sponsor, not part of a team, success page."""
    with tc(tid(19, shift)):
        with tc.step("Answer 'No' to formal complaint and license suspension, click 'Next'"):
            roa.formal_actions()
        tc.on_page("/professional-experience", "Professional Experience page opens")
        tc.progress(50)

    with tc(tid(20, shift)):
        with tc.step(f"Fill transactions, volume, type, NRDS ID '{PROFESSIONAL['nrds_id']}', "
                     f"brokerage '{PROFESSIONAL['brokerage']}', click 'Next'"):
            roa.professional_experience()
        tc.on_page("/sponsoring-agent", "Sponsoring Agent page opens")
        tc.progress(55)

    with tc(tid(21, shift)):
        popup = roa.sponsor_video_popup()
        tc.see_element(popup, "sponsor video popup (opens by itself)", timeout=10_000)
        tc.see("Find the Right Sponsor", root=popup)
        with tc.step("Close the video popup"):
            roa.close_sponsor_video()
        tc.see("Learn More About Sponsorship")

    with tc(tid(22, shift)):
        with tc.step("Leave sponsor blank, click 'Next'"):
            roa.next_without_sponsor()
        tc.see("Confirm: No Sponsor Selected", "I acknowledge that I am choosing not to name a sponsor",
               "Go Back", "Confirm")

    with tc(tid(23, shift)):
        with tc.step("Tick acknowledgement + 'Confirm' in both popups"):
            roa.confirm_no_sponsor()
        tc.on_page("/part-of-team", "'Are you a part of a team?' page opens")
        tc.progress(60)

    with tc(tid(24, shift)):
        with tc.step("Select 'No', click 'Next'"):
            roa.answer_radio("/part-of-team", "No")
        tc.on_page("/roa-application/success", "ROA Application success page opens")
        tc.progress(70)

    with tc(tid(25, shift)):
        tc.see("Congrats", user["full_name"], "Completed Your ROA Application", "View/Edit Your Responses",
               "Continue: Tax Information")


def roa_continue_to_tax(tc, roa, shift=0):
    with tc(tid(27, shift)):
        with tc.step("Click 'Continue: Tax Information' + confirm"):
            roa.success_page()
        tc.on_page("/tax-information", "Tax Information stage opens")
        tc.progress(70)
