import os
import re

from pages.base_page import BasePage

UPLOAD_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "test_data", "license_document.pdf")


class TransferLicensePage(BasePage):

    def complete(self):
        """Agent with an active license: confirm the transfer -> Pending Broker Review."""
        self.wait_for_page("/transfer-license")
        self.click(self.page.get_by_text("I confirm that I have transferred my", exact=False).first)
        self.confirm_popup()
        self.wait_visible(self.page.get_by_text("Pending Broker Review"))
        print("Done -> Pending Broker Review")

    def card_action(self, text):
        """'<State> License Transfer Instructions' / 'Upload Documents' on the license card (not real buttons)."""
        return self.page.get_by_text(text, exact=False).filter(visible=True).first

    def store_link(self, store):
        """App Store / Google Play badge in the ROA+ banner."""
        site = {"App Store": "apple.com", "Google Play": "play.google.com"}[store]
        return self.page.locator(f"a[href*='{site}'], img[alt='{store}']").first

    def upload_document(self, path=UPLOAD_FILE):
        """Click 'Upload Documents' and give it the file (direct file picker or an upload popup).
        Returns the file name."""
        try:
            with self.page.expect_file_chooser(timeout=5_000) as chooser:
                self.click(self.card_action("Upload Documents"))
            chooser.value.set_files(path)
        except Exception:
            # an upload popup opened instead -> use its file input, then its upload/submit button
            dialog = self.page.get_by_role("dialog")
            self.wait_visible(dialog)
            dialog.locator("input[type='file']").first.set_input_files(path)
            submit = dialog.get_by_role("button", name=re.compile(r"^(upload|submit|save|done)", re.I))
            self.page.wait_for_timeout(500)
            if submit.count():
                self.click(submit.first)
        return os.path.basename(path)
