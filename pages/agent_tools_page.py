from pages.base_page import BasePage


class AgentToolsPage(BasePage):

    def complete(self, add_free_crm=False):
        self.wait_for_page("/customize-agent-tools")
        self.click_if_present(self.button("Agree and Continue"), 10_000)     # "Stay Connected" popup
        if add_free_crm:
            self.add_free_crm()
        self.continue_to_payment()

    def stay_connected_popup(self):
        return self.page.get_by_role("dialog")

    def agree_and_continue(self):
        self.wait_for_page("/customize-agent-tools")
        self.click(self.button("Agree and Continue"))
        self.page.get_by_role("dialog").wait_for(state="hidden")

    def add_free_crm(self):
        if not self.page.get_by_text("Your Selected CRM Tool").is_visible():
            self.click(self.button("Add at No Additional Cost").first)
            self.wait_visible(self.page.get_by_text("Your Selected CRM Tool"))

    def continue_to_payment(self):
        self.click(self.button("Continue: Pay & Checkout"))
        self.confirm_popup_if_present()
        self.wait_for_page("/pay-and-checkout")
