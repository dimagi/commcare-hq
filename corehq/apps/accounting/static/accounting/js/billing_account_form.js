hqDefine('accounting/js/billing_account_form', [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'accounting/js/credits_tab',
    'hqwebapp/js/stay_on_tab',
], function (
    $,
    ko,
    initialPageData
) {
    var BillingAccountForm = function (is_active) {
        'use strict';
        var self = this;

        self.is_active = ko.observable(is_active);
        self.showActiveAccounts = ko.computed(function () {
            return !self.is_active();
        });
    };

    $(function () {
        var baForm = new BillingAccountForm(initialPageData.get('account_form_is_active'));
        $('#account-form').koApplyBindings(baForm);

        $("#show_emails").click(function() {
            $('#emails-text').show();
            $(this).parent().hide();
        });
    });
});
