from dummy_data import TAX, TAX_ADDRESS
from pages.base_page import BasePage


class TaxInformationPage(BasePage):

    def complete(self, user):
        self.open_w9_form()
        self.submit_w9(user)
        self.continue_to_ica()

    def open_w9_form(self):
        self.wait_for_page("/tax-information/step-1")
        self.click_next()
        self.wait_for_page("/tax-information/step-2")

    def ssn_box(self):
        return self.input("tax_information.taxpayer_id")

    def fill_w9(self, user):
        self.choose_radio("Individual")
        self.fill(self.input("tax_information.identity"), user["full_name"])
        ssn = self.ssn_box()
        self.fill(ssn, "")
        self.type_slowly(ssn, TAX["ssn"])
        self.select_dropdown("Tax Classification", TAX["classification"])
        self.fill(self.input("tax_information.address_line_1"), TAX_ADDRESS["line1"])
        # City and Zip Code are dropdowns that open only after a State is picked
        self.select_dropdown("State", TAX_ADDRESS["state"])
        self.select_dropdown_by_typing("City", TAX_ADDRESS["city"])
        self.select_dropdown_by_typing("Zip Code", TAX_ADDRESS["zip"])

    def submit_w9(self, user):
        self.fill_and_next(lambda: self.fill_w9(user))
        self.wait_for_page("/tax-information/step-3")

    def continue_to_ica(self):
        self.click(self.button("Continue: Sign Your ICA"))
        self.confirm_popup_if_present()
        self.wait_for_page("/sign-your-ica")
