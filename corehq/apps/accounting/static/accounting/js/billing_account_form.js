import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import "accounting/js/credits_tab";
import "accounting/js/widgets";

var billingAccountFormModel = function (isActive, isCustomerBillingAccount, enterpriseAdminEmails, isSmsBillableReportVisible) {
    var self = {};

    self.is_active = ko.observable(isActive);
    self.is_customer_billing_account = ko.observable(isCustomerBillingAccount);
    self.is_sms_billable_report_visible = ko.observable(isSmsBillableReportVisible);
    self.enterprise_admin_emails = ko.observable(enterpriseAdminEmails);
    self.showActiveAccounts = ko.computed(function () {
        return !self.is_active();
    });

    return self;
};

$(function () {
    var baForm = billingAccountFormModel(initialPageData.get('account_form_is_active'),
        initialPageData.get('is_customer_billing_account'), initialPageData.get('enterprise_admin_emails'),
        initialPageData.get('is_sms_billable_report_visible'));
    $('#account-form').koApplyBindings(baForm);

    $("#show_emails").click(function () {
        $('#emails-text').show();
        $(this).parent().hide();
    });
});
