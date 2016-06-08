hqDefine('accounting/js/accounting.subscription_info_handler.js', function () {
    var SubscriptionInfoHandler = function () {
        'use strict';
        var self = this;
        var AsyncSelect2Handler = hqImport('accounting/js/accounting.billing_info_handler.js').AsyncSelect2Handler;
        self.domain = new AsyncSelect2Handler('domain');
        self.account = new AsyncSelect2Handler('account');
        self.plan_version = new AsyncSelect2Handler('plan_version');

        self.init = function () {
            self.domain.init();
            self.account.init();
            self.plan_version.init();
            self.plan_version.getAdditionalData = function () {
                return {
                    'product': $('#id_plan_product').val(),
                    'edition': $('#id_plan_edition').val(),
                };
            };
            $(function () {
                var deselectPlanVersion = function () {
                    var $planVer = $('#id_plan_version');
                    $planVer.val('');
                    $planVer.select2('val', '');
                };
                $('#id_plan_product').change(deselectPlanVersion);
                $('#id_plan_edition').change(deselectPlanVersion);
            });
        };
    };

    return {
        initSubscriptionInfoHandler: function () {
            var subscriptionInfoHandler = new SubscriptionInfoHandler();
            subscriptionInfoHandler.init();
        },
    };
});
