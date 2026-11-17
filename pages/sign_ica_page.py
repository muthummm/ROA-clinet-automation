import re

from config import DEFAULT_TIMEOUT, SLOW_TIMEOUT
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

        esign = self.page.frame_locator(ESIGN_FRAME)
        self.click(esign.get_by_role("button", name="OK"))          # "not legally binding" popup
        self.click(esign.get_by_role("button", name="Get started"))

        self.fill_mandatory_fields(user)

        self.click(esign.locator(NEXT_BUTTON, has_text="Continue"))
        self.click(esign.locator(AGREE_BUTTON).or_(esign.get_by_role("button", name="I agree")).first)
        self.wait_visible(esign.get_by_text("Thanks for submitting your document!"), SLOW_TIMEOUT)

        # the app should move to the next page by itself - often it does not, so reload after 8s
        try:
            self.wait_for_page("/customize-agent-tools", timeout=8_000)
        except Exception:
            print("Still on Sign ICA after submitting, reloading page")
            self.page.reload()
            self.wait_for_page("/customize-agent-tools", timeout=SLOW_TIMEOUT)

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
