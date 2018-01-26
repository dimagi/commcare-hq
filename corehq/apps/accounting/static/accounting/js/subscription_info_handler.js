hqDefine('accounting/js/subscription_info_handler', function () {
    var SubscriptionInfoHandler = function () {
        'use strict';
        var self = this;
        var AsyncSelect2Handler = hqImport('accounting/js/billing_info_handler').AsyncSelect2Handler;
        self.domain = new AsyncSelect2Handler('domain');
        self.account = new AsyncSelect2Handler('account');
        self.plan_version = new AsyncSelect2Handler('plan_version');

        self.init = function () {
            self.domain.init();
            self.account.init();
            self.plan_version.init();
            self.plan_version.getAdditionalData = function () {
                return {
                    'edition': $('#id_plan_edition').val(),
                };
            };
            $(function () {
                var deselectPlanVersion = function () {
                    var $planVer = $('#id_plan_version');
                    $planVer.val('');
                    $planVer.select2('val', '');
                };
                $('#id_plan_edition').change(deselectPlanVersion);
            });
        };
    };

    $(function() {
        $( "#id_start_date" ).datepicker({ dateFormat: "yy-mm-dd" });
        $( "#id_end_date" ).datepicker({ dateFormat: "yy-mm-dd" });
        $( "#id_delay_invoice_until" ).datepicker({ dateFormat: "yy-mm-dd" });

       var subscriptionInfoHandler = new SubscriptionInfoHandler();
       subscriptionInfoHandler.init();
    });
});
