import datetime as dt
import uuid

from config import DEFAULT_TIMEOUT
from dummy_data import (ADDRESS, BOARDS, DATE_OF_BIRTH, EMERGENCY_CONTACT, LICENSE, NEW_LICENSE, PREFERRED_NAME,
                        PROFESSIONAL)
from pages.base_page import BasePage

NEWLY_LICENSED_NO_NUMBER = "I am a newly licensed agent (I do not have my license number)"


class RoaApplicationPage(BasePage):

    def complete(self, user):
        """Fill every page of the ROA Application (agent with an active license), in order."""
        self.about_yourself(user)
        self.residential_address()
        self.emergency_contact()
        self.answer_radio("/active-license", "Yes")
        self.answer_radio("/license-status", "I hold an active license")
        self.answer_radio("/licensed-in-multiple-states", "No")
        self.license_details()
        self.real_estate_boards()
        self.formal_actions()
        self.professional_experience()
        self.sponsoring_agent()
        self.answer_radio("/part-of-team", "No")
        self.success_page()

    # ---------- personal details ----------
    def wait_for_prefilled_details(self):
        """The form loads First Name / Phone from sign up a moment after the page opens."""
        self.wait_for_page("/roa-application/about-yourself")
        self.page.wait_for_function(
            """() => {
                const fn = document.querySelector("input[name='first_name']");
                const ph = document.querySelector("input[name='phone_number']");
                return fn && fn.value.trim() !== '' && ph && ph.value.trim() !== '';
            }""",
            timeout=DEFAULT_TIMEOUT,
        )

    def about_yourself(self, user, preferred_name=PREFERRED_NAME):
        self.wait_for_prefilled_details()

        def fill_form():
            self.fill(self.input("preferred_name"), preferred_name)
            date_box = self.page.locator("input[placeholder='MM/DD/YYYY']")
            try:
                date_box.click(timeout=10_000)
            except Exception:
                # something is covering the date box -> close it and open the calendar directly
                print("Date box covered, opening calendar another way")
                self.page.keyboard.press("Escape")
                date_box.dispatch_event("click")
            self.click(self.page.locator(f"div[role='option'][aria-label='{DATE_OF_BIRTH}']"))
        self.fill_and_next(fill_form)

    def residential_address(self):
        self.wait_for_page("/your-residential-address")

        def fill_form():
            self.fill(self.input("address_line_1"), ADDRESS["line1"])
            self.fill(self.input("address_line_2"), ADDRESS["line2"])
            # City and Zip Code are dropdowns that open only after a State is picked
            self.select_dropdown("State", ADDRESS["state"])
            self.select_dropdown_by_typing("City", ADDRESS["city"])
            self.select_dropdown_by_typing("Zip Code", ADDRESS["zip"])
        self.fill_and_next(fill_form)

    def emergency_contact(self):
        self.wait_for_page("/your-emergency-contact")

        def fill_form():
            self.fill(self.input("ec_name"), EMERGENCY_CONTACT["name"])
            self.fill(self.input("ec_phone_number"), EMERGENCY_CONTACT["phone"])
            self.select_first_option("Relationship", close_after=False)
            self.fill(self.input("ec_email"), EMERGENCY_CONTACT["email"])
        self.fill_and_next(fill_form)

    def answer_radio(self, path, answer):
        """Pages with one question: pick the answer and click Next."""
        self.wait_for_page(path)
        self.fill_and_next(lambda: self.choose_radio(answer))

    # ---------- license: agent with an active license ----------
    def license_details(self):
        self.wait_for_page("/licensed-details")
        license_number = f"TEST-{uuid.uuid4().hex[:12].upper()}"
        print("License number:", license_number)

        def fill_form():
            self.select_dropdown("Primary State", LICENSE["state"])
            self.select_dropdown("What type of license is it?", LICENSE["type"])
            self.fill(self.input("licenses.0.license_no"), license_number)
            dates = self.page.locator("input[placeholder='MM/DD/YYYY']")
            self.pick_date(dates.nth(0), LICENSE["expiry_days_from_today"])
            self.pick_date(dates.nth(1), LICENSE["transfer_days_from_today"])
        self.fill_and_next(fill_form)

    # ---------- license: several states (Real Estate License Details) ----------
    def fill_license_details(self, licenses):
        """licenses[0] = primary license, licenses[1:] = additional licenses (one block each, in order)."""
        boxes = self.page.locator("input[role='combobox']")
        dates = self.page.locator("input[placeholder='MM/DD/YYYY']")
        for i, lic in enumerate(licenses):
            self.select_in_combobox(boxes.nth(2 * i), lic["state"])
            self.select_in_combobox(boxes.nth(2 * i + 1), lic["type"])
            self.fill(self.input(f"licenses.{i}.license_no"), lic["number"])
            self.pick_date(dates.nth(2 * i), lic["expiry_days_from_today"])
            self.pick_date(dates.nth(2 * i + 1), lic["transfer_days_from_today"])

    def select_board_option(self, index, text):
        """Boards page has one Board and one MLS dropdown per state: 0 = 1st state Board, 1 = 1st state MLS,
        2 = 2nd state Board ... Options read '<name> Active/Inactive', so pick by the name only."""
        box = self.page.locator("input[role='combobox']").nth(index)
        self.wait_visible(box).focus()
        self.page.keyboard.press("ArrowDown")
        option = self.page.locator("[role='option']", has_text=text).first
        self.click(option)
        self.page.keyboard.press("Escape")

    # ---------- license: newly licensed agent WITHOUT a license number ----------
    def issue_date_box(self):
        return self.page.locator("input[placeholder='Select Date']")

    def newly_licensed_without_number(self, days_from_today=NEW_LICENSE["issue_days_from_today"]):
        """License Status page: pick the option, then the Expected License Issuance Date.
        Returns the date as shown in the box (MM/DD/YYYY)."""
        self.wait_for_page("/license-status")
        date = (dt.date.today() + dt.timedelta(days=days_from_today)).strftime("%m/%d/%Y")

        def fill_form():
            self.choose_radio(NEWLY_LICENSED_NO_NUMBER)
            self.pick_date(self.issue_date_box(), days_from_today)
        self.fill_and_next(fill_form)
        return date

    def upcoming_license(self):
        """'Tell us about your upcoming license': State + Type of License (date comes prefilled)."""
        self.wait_for_page("/new-agent-license-info")
        state = self.page.locator("input[name='new_license_state']")
        license_type = self.page.locator("input[name='new_license_type']")
        # wait until the page has loaded its saved data (the date gets prefilled), else it wipes our choices
        self.page.wait_for_function("() => document.querySelector(\"input[placeholder='Select Date']\")?.value",
                                    timeout=DEFAULT_TIMEOUT)
        self.wait_until_ready(3000)

        def fill_form():
            if state.input_value() != NEW_LICENSE["state"]:
                self.select_dropdown("State", NEW_LICENSE["state"])
                # Type of License options load for the chosen state
                self.page.wait_for_function("el => el.value !== ''", arg=state.element_handle(), timeout=10_000)
                self.wait_until_ready(2000)
            if license_type.input_value() == "":
                self.select_dropdown("Type of License", NEW_LICENSE["type"])
        self.fill_and_next(fill_form)

    # ---------- boards / formal actions / experience ----------
    def real_estate_boards(self):
        self.wait_for_page("/real-estate-boards")

        def fill_form():
            self.select_dropdown_containing("Real Estate Boards / Associations", BOARDS["board"])
            self.select_dropdown_containing("Multiple Listing Service (MLS)", BOARDS["mls"])
        self.fill_and_next(fill_form)

    def select_boards(self):
        """Pick Board and MLS without clicking Next (to check the chips first)."""
        self.wait_for_page("/real-estate-boards")
        self.page.wait_for_timeout(1500)
        self.select_dropdown_containing("Real Estate Boards / Associations", BOARDS["board"])
        self.select_dropdown_containing("Multiple Listing Service (MLS)", BOARDS["mls"])

    def formal_actions(self):
        self.wait_for_page("/formal-actions")

        def fill_form():                       # answer "No" to every question
            no_answers = self.page.locator("//label[.//p[normalize-space()='No']]")
            self.wait_visible(no_answers.first)
            for i in range(no_answers.count()):
                self.click(no_answers.nth(i))
        self.fill_and_next(fill_form)

    def professional_experience(self):
        self.wait_for_page("/professional-experience")

        def fill_form():
            self.select_dropdown("How many transactions have you closed", PROFESSIONAL["transactions_36m"])
            self.select_dropdown("Select Transaction Count", PROFESSIONAL["transaction_count"])
            self.select_dropdown("What is your production volume", PROFESSIONAL["volume_12m"])
            self.select_dropdown("What type of transactions", PROFESSIONAL["transaction_type"], close_after=True)
            self.fill(self.input("nrds_id"), PROFESSIONAL["nrds_id"])
            self.fill(self.input("affiliated_brokerage"), PROFESSIONAL["brokerage"])
        self.fill_and_next(fill_form)

    # ---------- sponsoring agent: continue without a sponsor ----------
    def sponsor_video_popup(self):
        return self.page.get_by_role("dialog")

    def close_sponsor_video(self):
        self.wait_for_page("/sponsoring-agent")
        self.click_if_present(self.page.get_by_role("dialog").get_by_role("button", name="Close"), 8_000)

    def next_without_sponsor(self):
        """Click Next with an empty sponsor box -> 'Confirm: No Sponsor Selected' popup."""
        self.click(self.next_button())
        self.wait_visible(self.page.get_by_text("I acknowledge that I am choosing not to name a sponsor."))

    def confirm_no_sponsor(self):
        """Tick + Confirm in both popups -> 'Are you a part of a team?' page."""
        self.click(self.page.get_by_text("I acknowledge that I am choosing not to name a sponsor."))
        self.confirm_popup()
        self.wait_visible(self.page.get_by_text("No Sponsor Selected").first)

        self.click(self.next_button())
        self.click(self.page.get_by_text("I acknowledge that I did not select any sponsor"))
        old_url = self.page.url
        self.confirm_popup()
        self.wait_for_url_change(old_url)

    def sponsoring_agent(self):
        self.close_sponsor_video()
        self.next_without_sponsor()
        self.confirm_no_sponsor()

    # ---------- success page ----------
    def success_page(self):
        self.wait_for_page("/roa-application/success")
        self.click(self.button("Continue: Tax Information"))
        self.confirm_popup()
