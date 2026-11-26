from config import NAV_TIMEOUT, PASSWORD
from dummy_data import PRIMARY_STATE, new_user
from pages.base_page import BasePage


class SignUpPage(BasePage):
    """Sign Up step 1/2 (email + OTP) and step 2/2 (account details)."""

    def otp_boxes(self):
        return self.page.locator("input[aria-label='Please enter your pin code']")

    def get_started(self):
        return self.page.locator("//button[@type='submit' and normalize-space()='Get started']")

    # ---------- step 1/2 ----------
    def open_sign_up(self):
        self.open("/sign-up?step=1")
        self.wait_visible(self.input("email"))

    def submit_email(self, email):
        """Type the email, click Get started, wait for the 'Verify your email' popup."""
        self.fill(self.input("email"), email)
        otp_box = self.otp_boxes().first
        for attempt in range(1, 4):
            if otp_box.is_visible():
                return                                   # popup opened late (slow server)
            self.click(self.get_started())
            try:
                self.wait_visible(otp_box)
                return
            except Exception:
                print(f"OTP box did not show (attempt {attempt}), clicking Get started again")
        raise AssertionError("'Verify your email' popup did not open")

    def verify_otp(self):
        self.enter_otp()
        self.click(self.page.locator("//button[@type='button' and normalize-space()='Continue']"))
        self.wait_visible(self.input("first_name"))

    # ---------- step 2/2 ----------
    def fill_account_details(self, user):
        self.fill(self.input("first_name"), user["first_name"])
        self.fill(self.input("last_name"), user["last_name"])
        self.fill(self.input("phone_number"), user["phone_number"])
        self.select_dropdown("Primary State", PRIMARY_STATE)
        self.fill(self.page.locator("input[name='password']"), PASSWORD)
        self.fill(self.page.locator("input[name='confirm_password']"), PASSWORD)

    def create_account(self):
        self.click(self.get_started())
        self.page.wait_for_url("**/roa-application/about-yourself**", timeout=NAV_TIMEOUT, wait_until="commit")

    # ---------- whole sign up in one go (used by other tests) ----------
    def sign_up(self, user):
        self.open_sign_up()
        self.submit_email(user["email"])
        self.verify_otp()
        self.fill_account_details(user)
        self.create_account()

    def create_new_user(self):
        """Sign up a new user. If the email/phone is already used, try the next one (max 5)."""
        for attempt in range(1, 6):
            user = new_user()
            print("User:", user["full_name"], "|", user["email"], "|", user["phone_number"])
            try:
                self.sign_up(user)
                return user
            except Exception:
                print(f"Sign-up failed for {user['email']} (attempt {attempt}), trying next user")
                self.page.context.clear_cookies()
        raise AssertionError("Sign-up failed 5 times")
