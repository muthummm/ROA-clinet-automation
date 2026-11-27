# ============================================================
# BASE PAGE - common actions used by every page
# Every page class starts with:  class MyPage(BasePage):
# Every action first WAITS until the element is visible.
# ============================================================
import datetime as dt
import time

from config import BASE_URL, DEFAULT_TIMEOUT, NAV_TIMEOUT, OTP


class BasePage:
    def __init__(self, page):
        self.page = page

    # ---------- open / wait for pages ----------
    def open(self, path):
        self.page.goto(BASE_URL + path, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

    def wait_for_page(self, path, timeout=NAV_TIMEOUT):
        self.page.wait_for_url(f"**{path}**", timeout=timeout)
        print("On page:", self.page.url)

    def wait_until_ready(self, max_ms=1500):
        """Wait until the page stops loading data (usually well under 1s), but never longer than max_ms."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=max_ms)
        except Exception:
            pass

    def wait_for_url_change(self, old_url, timeout=NAV_TIMEOUT):
        self.page.wait_for_url(lambda url: url != old_url, timeout=timeout, wait_until="commit")

    # ---------- click / type ----------
    def wait_visible(self, locator, timeout=DEFAULT_TIMEOUT):
        locator.wait_for(state="visible", timeout=timeout)
        return locator

    def click(self, locator, timeout=DEFAULT_TIMEOUT):
        self.wait_visible(locator, timeout).click()

    def click_if_present(self, locator, timeout=5_000):
        try:
            self.click(locator, timeout)
        except Exception:
            pass

    def fill(self, locator, value, timeout=DEFAULT_TIMEOUT):
        self.wait_visible(locator, timeout).fill(value)

    def type_slowly(self, locator, value):
        """For masked fields (SSN) where fill() does not work."""
        self.click(locator)
        locator.press_sequentially(value, delay=80)

    # ---------- find elements ----------
    def input(self, name):
        """<input name='...'>"""
        return self.page.locator(f"input[name='{name}']")

    def button(self, text):
        """Visible button that contains this text."""
        return self.page.locator("button:visible", has_text=text)

    def next_button(self):
        return self.page.locator("//button[@type='submit' and normalize-space()='Next']")

    # ---------- Next button ----------
    def click_next(self):
        old_url = self.page.url
        self.click(self.next_button())
        self.wait_for_url_change(old_url)

    def wait_while_saving(self, start_url, max_ms=45_000):
        """After clicking Next: True when the page moved on within max_ms.
        A slow server first saves the form, then reloads the stage list, and only then opens the next
        page (seen: 15s+), so the 'Next' spinner stopping does not mean the page will not change."""
        try:
            self.wait_for_url_change(start_url, timeout=max_ms)
            return True
        except Exception:
            return False

    def fill_and_next(self, fill_form, attempts=3):
        """Fill the form, click Next. Some forms reset themselves after loading,
        so if the page did not change we fill it again (max 3 times)."""
        # forms load their saved data after the page opens (slow server: several seconds) and would wipe
        # what we type -> wait until the page stops loading data, plus a short moment for it to re-render
        self.wait_until_ready(15_000)
        self.page.wait_for_timeout(700)
        start_url = self.page.url
        for attempt in range(1, attempts + 1):
            if self.page.url != start_url:
                return                                  # an earlier (slow) save went through
            try:
                fill_form()
                self.click(self.next_button())
            except Exception as error:
                if self.page.url != start_url:
                    return                              # page moved on while we were filling again
                if attempt == attempts:
                    raise
                print(f"Filling the form failed (attempt {attempt}): {str(error).splitlines()[0][:120]}")
                self.page.keyboard.press("Escape")
                self.wait_until_ready(10_000)
                continue
            # a slow server can take a while to save -> wait while 'Next' shows its loading spinner
            if self.wait_while_saving(start_url):
                return
            print(f"Form not submitted (attempt {attempt}), filling again")
        raise AssertionError(f"Could not submit form on {self.page.url}")

    # ---------- dropdowns / radio buttons ----------
    def dropdown(self, label):
        return self.page.locator(
            f"xpath=//label[contains(normalize-space(), \"{label}\")]/following::input[@role='combobox'][1]"
        )

    def open_dropdown(self, label):
        self.wait_visible(self.dropdown(label)).focus()
        self.page.keyboard.press("ArrowDown")

    def select_dropdown(self, label, option, close_after=False):
        """Pick the option with exactly this text (opens the list again if it did not open)."""
        choice = self.page.get_by_role("option", name=option, exact=True)
        for attempt in range(1, 4):
            self.open_dropdown(label)
            try:
                self.wait_visible(choice, 10_000)
                break
            except Exception:
                print(f"Dropdown '{label}' did not open (attempt {attempt}), trying again")
                self.dropdown(label).click()
        self.click(choice)
        if close_after:
            self.page.keyboard.press("Escape")

    def select_in_combobox(self, box, option):
        """Pick an option in a given dropdown (for pages with several dropdowns that have the same label)."""
        choice = self.page.get_by_role("option", name=option, exact=True)
        for attempt in range(1, 4):
            self.wait_visible(box).focus()
            self.page.keyboard.press("ArrowDown")
            try:
                self.wait_visible(choice, 5_000)
                break
            except Exception:
                print(f"Dropdown did not open (attempt {attempt}), trying again")
                box.click()
        self.click(choice)

    def select_dropdown_by_typing(self, label, option):
        """Long lists (City, Zip Code): type to filter, then pick the option."""
        box = self.wait_visible(self.dropdown(label))
        self.page.wait_for_function("el => !el.disabled", arg=box.element_handle(), timeout=DEFAULT_TIMEOUT)
        self.page.keyboard.press("Escape")           # close any list still open (it covers this box)
        box.focus()                                  # focus, not click: a click can be blocked by an overlay
        box.press_sequentially(option, delay=30)
        exact = self.page.get_by_role("option", name=option, exact=True)
        partial = self.page.locator("[role='option']", has_text=option)
        self.click(exact.or_(partial).first)

    def select_dropdown_containing(self, label, text):
        """Multi-select: pick the option that contains this text (skip if already picked)."""
        self.open_dropdown(label)
        self.wait_visible(self.page.locator("[role='option']").first)
        option = self.page.locator("[role='option']", has_text=text)
        if option.count():
            option.first.click()
        self.page.keyboard.press("Escape")

    def select_first_option(self, label, close_after=True):
        self.open_dropdown(label)
        self.click(self.page.locator("[role='option']").first)
        if close_after:
            self.page.keyboard.press("Escape")

    def choose_radio(self, text):
        self.click(self.page.locator(f"//label[.//p[normalize-space()='{text}']]").first)

    def click_and_catch(self, locator, wait_ms=8_000):
        """Click something that may open a new tab, start a download or change the page.
        Returns {"page": new_tab} / {"download": download} / {"navigated": True} / {} (nothing happened)."""
        caught = {}
        on_page = lambda p: caught.setdefault("page", p)
        on_download = lambda d: caught.setdefault("download", d)
        self.page.context.on("page", on_page)
        self.page.on("download", on_download)
        old_url = self.page.url
        try:
            self.click(locator)
            end = time.time() + wait_ms / 1000
            while time.time() < end and not caught:
                if self.page.url != old_url:
                    caught["navigated"] = True
                    break
                self.page.wait_for_timeout(200)
        finally:
            self.page.context.remove_listener("page", on_page)
            self.page.remove_listener("download", on_download)
        return caught

    # ---------- popups ----------
    def confirm_popup(self, timeout=DEFAULT_TIMEOUT):
        self.click(self.page.get_by_role("dialog").get_by_role("button", name="Confirm"), timeout)

    def confirm_popup_if_present(self):
        try:
            self.confirm_popup(timeout=5_000)
        except Exception:
            pass

    # ---------- OTP / calendar ----------
    def enter_otp(self):
        boxes = self.page.locator("input[aria-label='Please enter your pin code']")
        self.wait_visible(boxes.first)
        for i, digit in enumerate(OTP):
            self.fill(boxes.nth(i), digit)

    def pick_date(self, date_input, days_from_today):
        """Open the calendar and click the date (typing a date does not work)."""
        date = dt.date.today() + dt.timedelta(days=days_from_today)
        day = date.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        label = f"Choose {date.strftime('%A, %B')} {day}{suffix}, {date.year}"

        self.click(date_input)
        day_cell = self.page.locator(f"div[role='option'][aria-label='{label}']")
        for _ in range(60):
            if day_cell.count() and day_cell.first.is_visible():
                day_cell.first.click()
                return
            self.click(self.page.get_by_role("button", name="Next Month"))
        raise AssertionError(f"Date not found in calendar: {label}")
