import re

from config import DEFAULT_TIMEOUT
from pages.base_page import BasePage

ESIGN_FRAME = "iframe[name='x-hellosign-embedded']"
REQUIRED = ":has([class*='__required--'])"      # Dropbox Sign marks mandatory fields like this
# Dropbox Sign buttons: older version uses data-qa-ref, newer uses data-testid -> accept both
NEXT_BUTTON = "[data-qa-ref='button-next'], [data-testid='button-next']"
AGREE_BUTTON = "[data-qa-ref='button-agree'], [data-testid='button-agree']"


class SignIcaPage(BasePage):

    def complete(self, user):
        self.wait_for_page("/sign-your-ica")
        self.open_esign()
        self.start_signing()
        self.fill_mandatory_fields(user)
        self.submit()
        self.close_after_submit()

    def esign(self):
        return self.page.frame_locator(ESIGN_FRAME)

    def start_signing(self):
        """Close the 'not legally binding' popup and click Get started."""
        esign = self.esign()
        self.click(esign.get_by_role("button", name="OK"))
        self.click(esign.get_by_role("button", name="Get started"))

    def fields_left(self):
        """'13 required fields left' counter (found by its text - its CSS class changes)."""
        return self.esign().locator("span", has_text=re.compile(r"^\s*\d+ required fields? left\s*$")).first

    def open_first_initials(self):
        """Click the first required initials field -> 'Add your initials' window."""
        esign = self.esign()
        self.wait_visible(self.fields_left())
        field = esign.locator(f"[data-qa-ref='field-initials']{REQUIRED} [data-qa-ref='initials-input']",
                              has_text="Click to initial").first
        self.wait_visible(field)
        field.scroll_into_view_if_needed()
        self.click(field)
        self.wait_visible(esign.get_by_role("tab", name="Type"))

    def insert_initials_everywhere(self, user):
        """In the open initials window: Type tab -> initials -> 'Fill in all fields' (insert everywhere)."""
        before = self.fields_left().inner_text().strip()
        self.type_signature(user["initials"], True, self.fields_left(), before)
        self.wait_counter_change(self.fields_left(), before)
        self.page.wait_for_timeout(800)     # 'Insert everywhere' fills the other pages a moment later

    def submit(self):
        esign = self.esign()
        self.click(esign.locator(NEXT_BUTTON, has_text="Continue"))
        self.click(esign.locator(AGREE_BUTTON).or_(esign.get_by_role("button", name="I agree")).first)
        self.wait_visible(esign.get_by_text("Thanks for submitting your document!"))

    def close_after_submit(self):
        """Click Close in the e-sign window (if shown) and wait for the ICA success page or the next stage.
        Returns 'success' (Sign Your ICA success page) or 'next' (app went straight to Agent Tools)."""
        self.click_if_present(self.esign().get_by_role("button", name="Close"), 5_000)
        success = self.page.get_by_text("Signed your ICA", exact=False)
        for attempt in range(2):
            for _ in range(40):                                   # max ~12s
                if success.count() and success.first.is_visible():
                    return "success"
                if "/customize-agent-tools" in self.page.url:
                    return "next"
                self.page.wait_for_timeout(300)
            if attempt == 0:
                print("ICA success page not shown after submitting, reloading page")
                self.page.reload(wait_until="domcontentloaded")
        raise AssertionError(f"After signing: no ICA success page ({self.page.url})")

    def continue_to_agent_tools(self):
        if "/customize-agent-tools" not in self.page.url:
            self.click(self.button("Continue: Customize Agent Tools"))
            self.confirm_popup_if_present()
        self.wait_for_page("/customize-agent-tools")

    def open_esign(self, attempts=6):
        """Open the Dropbox Sign window and wait until it has fully loaded (its 'OK' popup shows).

        - Wait for the page to settle first: clicking too early lets a page refresh close the window.
        - Only click when NO e-sign window exists (a 2nd click opens a 2nd, empty window).
        - If the window does not load, reload the page and try again.
        """
        button = self.page.get_by_role("button", name="Continue to E-Sign ICA")
        frame = self.page.locator(ESIGN_FRAME)
        ok_button = self.page.frame_locator(ESIGN_FRAME).get_by_role("button", name="OK")

        for attempt in range(1, attempts + 1):
            self.wait_visible(button)
            self.wait_until_ready(3000)                     # let the page finish loading
            for _ in range(50):                             # check every 0.5s, max 25s
                if ok_button.count() and ok_button.is_visible():
                    assert frame.count() == 1, "More than one e-sign window is open"
                    return                                  # e-sign document loaded
                if frame.count() == 0 and button.count() and button.is_visible():
                    # no e-sign window (not opened yet, or a page refresh closed it) -> click again
                    try:
                        button.click(timeout=5_000)
                    except Exception:
                        pass
                self.page.wait_for_timeout(500)
            print(f"E-sign window did not load (attempt {attempt}), reloading page")
            self.page.reload()
        raise AssertionError("E-sign window never loaded")

    def counter_changed(self, counter, before):
        return counter.count() == 0 or not counter.is_visible() or counter.inner_text().strip() != before

    def wait_counter_change(self, counter, before, timeout_ms=3000):
        """Wait until the 'required fields left' counter changes (checks every 0.2s)."""
        for _ in range(timeout_ms // 200):
            if self.counter_changed(counter, before):
                return True
            self.page.wait_for_timeout(200)
        return False

    def type_signature(self, text, insert_everywhere, counter, before):
        esign = self.page.frame_locator(ESIGN_FRAME)
        type_tab = esign.get_by_role("tab", name="Type")
        # either the signing window opens, or the saved signature is used straight away
        for _ in range(40):                                 # max 8s
            if type_tab.count() and type_tab.is_visible():
                break
            if self.counter_changed(counter, before):
                return                                      # signature already remembered
            self.page.wait_for_timeout(200)
        else:
            return
        type_tab.click()
        self.fill(esign.locator("input[data-qa-ref='signing-modal--type-in-field']"), text)
        if insert_everywhere:
            self.click(esign.get_by_test_id("insert-everywhere-btn"))
        else:
            self.click(esign.get_by_test_id("singing-modal--insert-btn"))
        type_tab.wait_for(state="hidden", timeout=DEFAULT_TIMEOUT)

    def fill_mandatory_fields(self, user):
        esign = self.page.frame_locator(ESIGN_FRAME)
        initials = esign.locator(f"[data-qa-ref='field-initials']{REQUIRED} [data-qa-ref='initials-input']",
                                 has_text="Click to initial")
        signatures = esign.locator(f"[data-qa-ref='field-signature']{REQUIRED} [data-qa-ref='signature-input']",
                                   has_text="Click to sign")
        checkboxes = esign.locator(f"[data-qa-ref='field-checkbox']{REQUIRED}"
                                   ":has(input[data-qa-ref='checkbox']:not(:checked))")
        # "13 required fields left" counter (found by its text - its CSS class changes)
        fields_left = esign.locator("span", has_text=re.compile(r"^\s*\d+ required fields? left\s*$")).first
        self.wait_visible(fields_left)
        self.wait_visible(esign.locator("[data-qa-ref='page-0']"))
        # wait until the fields are drawn on the document (the counter shows up before them)
        self.wait_visible(esign.locator(f"[data-qa-ref^='field-']{REQUIRED}").first)
        self.page.wait_for_timeout(500)

        # skip[kind] = how many fields of that kind did NOT change the counter when clicked
        # (already filled / not really required) -> next time click the following one instead
        skip = {"initials": 0, "signature": 0, "checkbox": 0}
        stuck = 0
        for _ in range(40):
            if fields_left.count() == 0 or not fields_left.is_visible():
                break                                   # all mandatory fields done
            before = fields_left.inner_text().strip()
            if before.startswith("0 "):
                break
            print("Mandatory fields left:", before)

            if initials.count() > skip["initials"]:
                kind, field = "initials", initials.nth(skip["initials"])
            elif signatures.count() > skip["signature"]:
                kind, field = "signature", signatures.nth(skip["signature"])
            elif checkboxes.count() > skip["checkbox"]:
                kind, field = "checkbox", checkboxes.nth(skip["checkbox"])
            else:
                # remaining fields are on pages not loaded yet -> jump to the next field
                self.click(esign.locator(NEXT_BUTTON).first)
                self.page.wait_for_timeout(1500)
                stuck += 1
                if stuck >= 15:
                    raise AssertionError(f"Signing stuck at {before} fields")
                continue

            field.scroll_into_view_if_needed()
            self.click(field)
            if kind == "initials":
                self.type_signature(user["initials"], True, fields_left, before)
            elif kind == "signature":
                self.type_signature(user["full_name"], False, fields_left, before)
            changed = self.wait_counter_change(fields_left, before)
            if changed and kind == "initials":
                self.page.wait_for_timeout(800)     # 'Insert everywhere' fills the other pages a moment later

            if not changed:
                # nothing changed: close any 'Edit / Clear' menu and try the next field
                self.page.keyboard.press("Escape")
                skip[kind] += 1
                stuck += 1
                print(f"{kind} field did not count, trying the next one")
                if stuck >= 15:
                    raise AssertionError(f"Signing stuck at {before} fields")
            else:
                stuck = 0
                skip = {"initials": 0, "signature": 0, "checkbox": 0}
