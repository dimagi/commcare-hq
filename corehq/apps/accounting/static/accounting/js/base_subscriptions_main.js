hqDefine('accounting/js/base_subscriptions_main', [
    'jquery',
    'knockout',
    'accounting/js/widgets',
    'hqwebapp/js/stay_on_tab',
    'accounting/js/credits_tab',
    'jquery-ui/ui/datepicker',
], function(
    $,
    ko,
    widgets
) {
    var SubscriptionInfoHandler = function() {
        'use strict';
        var self = {};

        var AsyncSelect2Handler = widgets.AsyncSelect2Handler;
        self.domain = AsyncSelect2Handler('domain');
        self.account = AsyncSelect2Handler('account');
        self.plan_version = AsyncSelect2Handler('plan_version');

        self.init = function() {
            self.domain.init();
            self.account.init();
            self.plan_version.init();
            self.plan_version.getAdditionalData = function() {
                return {
                    'edition': $('#id_plan_edition').val(),
                };
            };
            $(function() {
                var deselectPlanVersion = function() {
                    var $planVer = $('#id_plan_version');
                    $planVer.val('');
                    $planVer.select2('val', '');
                };
                $('#id_plan_edition').change(deselectPlanVersion);
            });
        };

        return self;
    };

    var InvoiceModel = function() {
        var self = {};
        var invoice = $('#id_do_not_invoice').prop("checked");
        self.noInvoice = ko.observable(invoice);
        return self;
    };

    $(function() {
        $("#id_start_date").datepicker({
            dateFormat: "yy-mm-dd",
        });
        $("#id_end_date").datepicker({
            dateFormat: "yy-mm-dd",
        });
        $("#id_delay_invoice_until").datepicker({
            dateFormat: "yy-mm-dd",
        });

        var subscriptionInfoHandler = SubscriptionInfoHandler();
        subscriptionInfoHandler.init();

        var invoiceModel = InvoiceModel();
        // fieldset is not unique enough a css identifier
        // historically this has taken the first one without checking
        // todo: use a more specific identifier to make less brittle
        $('fieldset').first().koApplyBindings(invoiceModel);
    });
});
