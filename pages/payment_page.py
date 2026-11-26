from dummy_data import CARD
from pages.base_page import BasePage


class PaymentPage(BasePage):

    def complete(self, user):
        self.fill_card(user)
        self.pay()
        self.continue_to_roa_email()

    def stripe(self):
        return self.page.frame_locator("iframe[name='embedded-checkout']")

    def wait_for_checkout(self):
        self.wait_for_page("/pay-and-checkout")
        self.wait_visible(self.stripe().locator("#cardNumber"))
        # safety: only pay on a Stripe TEST checkout
        assert any("publishableKey=pk_test_" in frame.url for frame in self.page.frames), \
            "Stripe is NOT in test mode - stopping."

    def fill_card(self, user):
        self.wait_for_checkout()
        stripe = self.stripe()
        self.fill(stripe.locator("#cardNumber"), CARD["number"])
        self.fill(stripe.locator("#cardExpiry"), CARD["expiry"])
        self.fill(stripe.locator("#cardCvc"), CARD["cvc"])
        self.fill(stripe.locator("#billingName"), user["full_name"])
        self.wait_visible(stripe.locator("#billingCountry")).select_option(CARD["country"])
        zip_box = stripe.locator("#billingPostalCode")
        if zip_box.count() and zip_box.is_visible():     # Stripe asks a ZIP for US cards
            self.fill(zip_box, CARD["zip"])

        save_info = stripe.locator("#enableStripePass")
        if save_info.count() and save_info.is_checked():
            save_info.uncheck()

    def pay(self):
        """Click Pay (retry up to 3 times) and wait until the page moves on."""
        stripe = self.stripe()
        self.page.wait_for_timeout(1000)
        old_url = self.page.url
        pay = stripe.locator("button[type='submit']", has_text="Pay").first
        for attempt in range(1, 4):
            self.wait_visible(pay).scroll_into_view_if_needed()
            pay.click()
            try:
                self.wait_for_url_change(old_url, timeout=45_000)
                return
            except Exception:
                print(f"Payment not done yet (attempt {attempt}), clicking Pay again")
        raise AssertionError("Payment did not complete")

    def continue_to_roa_email(self, timeout_seconds=60):
        """After paying, staging shows 'Your Payment was a Success!' with a
        'Continue: Setup Your ROA Email' button. Click it (+ confirm popup).
        If the app goes straight to the ROA email page, nothing to click."""
        continue_button = self.button("Continue: Setup Your ROA Email")
        for _ in range(timeout_seconds):
            if "/setup-roa-email" in self.page.url:
                return                                  # reached the ROA email page
            if continue_button.count() and continue_button.first.is_visible():
                print("Payment success page -> Continue: Setup Your ROA Email")
                try:
                    # short click: the page may move on by itself and remove the button
                    continue_button.first.click(timeout=5_000)
                    self.confirm_popup_if_present()
                except Exception:
                    pass
            self.page.wait_for_timeout(1000)
        raise AssertionError(f"After payment: ROA email page did not open ({self.page.url})")
