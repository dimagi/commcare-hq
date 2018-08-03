hqDefine('accounting/js/confirm_plan', function () {
    var confirmPlanModel = function (isUpgrade, nextInvoiceDate, currentPlan, newPlan, isDowngradeBeforeMinimum,
                                     currentSubscriptionEndDate) {
        'use strict';
        var self = {};
        self.isUpgrade = isUpgrade;
        self.nextInvoiceDate = nextInvoiceDate;                         // TODO: Delete if unnecessary
        self.currentPlan = currentPlan;
        self.newPlan = newPlan;
        self.isDowngradeBeforeMinimum = isDowngradeBeforeMinimum;       // TODO: Delete if unnecessary
        self.currentSubscriptionEndDate = currentSubscriptionEndDate;   // TODO: Delete if unnecessary

        self.openDowngradeModal = function(confirmPlanModel) {
            if (confirmPlanModel.isUpgrade) {
                self.submitPlanChange();
            } else {
                var $modal = $("#modal-downgrade");
                $modal.modal('show');
            }
        };
        self.submitDowngrade = function(pricingTable, e) {
            var finish = function() {
                self.submitPlanChange();
            };

            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                method: "POST",
                url: hqImport('hqwebapp/js/initial_page_data').reverse('email_on_downgrade'),
                data: {
                    old_plan: self.currentPlan.name,
                    new_plan: self.newPlan.name,
                    note: $button.closest(".modal").find("textarea").val(),
                },
                success: finish,
                error: finish
            });
        };
        self.submitPlanChange = function () {
            var success = function () {
                console.log("Success in confirm_billing_account_info");
            };
            var error = function () {
                console.log("Error in confirm_billing_account_info");
            };

            $.ajax({
                method: "POST",
                class: "form",
                // data: {plan_edition: self.newPlan.edition},
                data: new FormData($(this)),
                url: hqImport('hqwebapp/js/initial_page_data').reverse('confirm_billing_account_info'),
                success: success,
                error: error
            });
        };

        return self;
    };


    $(function () {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get;
        confirmPlanModel = confirmPlanModel(
            initial_page_data('is_upgrade'),
            initial_page_data('next_invoice_date'),
            initial_page_data('current_plan'),
            initial_page_data('new_plan'),
            initial_page_data('is_downgrade_before_minimum'),
            initial_page_data('current_subscription_end_date')
        );
        $('#confirm-plan').koApplyBindings(confirmPlanModel);
        $('#modal-downgrade').koApplyBindings(confirmPlanModel);
    }());
});
