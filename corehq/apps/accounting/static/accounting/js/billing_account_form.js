hqDefine('accounting/js/billing_account_form', function () {
    var BillingAccountForm = function (is_active) {
        'use strict';
        var self = this;

        self.is_active = ko.observable(is_active);
        self.showActiveAccounts = ko.computed(function () {
            return !self.is_active();
        });
    };

    $(function () {
        var baForm = new BillingAccountForm(hqImport('hqwebapp/js/initial_page_data').get('account_form_is_active'));
        $('#account-form').koApplyBindings(baForm);

        $("#show_emails").click(function() {
            $('#emails-text').show();
            $(this).parent().hide();
        });
    });
});
