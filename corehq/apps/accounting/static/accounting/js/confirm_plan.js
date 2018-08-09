hqDefine('accounting/js/confirm_plan', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    var confirmPlanModel = function (isUpgrade, currentPlan, newPlan) {
        'use strict';
        var self = {};

        self.isUpgrade = isUpgrade;
        self.currentPlan = currentPlan;
        self.newPlan = newPlan;

        self.form = undefined;
        self.openDowngradeModal = function(confirmPlanModel, e) {
            self.form = $(e.currentTarget).closest("form");
            if (confirmPlanModel.isUpgrade) {
                self.form.submit();
            } else {
                var $modal = $("#modal-downgrade");
                $modal.modal('show');
            }
        };
        self.submitDowngrade = function(pricingTable, e) {
            var finish = function() {
                if (self.form) {
                    self.form.submit();
                }
            };

            var $button = $(e.currentTarget);
            $button.disableButton();
            $.ajax({
                method: "POST",
                url: initialPageData.reverse('email_on_downgrade'),
                data: {
                    old_plan: self.currentPlan.name,
                    new_plan: self.newPlan.name,
                    note: $button.closest(".modal").find("textarea").val(),
                },
                success: finish,
                error: finish,
            });
        };

        self.init = function () {
            var userAgreementCheckBox = document.getElementById('user-agreement');
            var confirmPlanButton = document.getElementById('confirm-plan');
            if (userAgreementCheckBox !== null) {
                confirmPlanButton.disabled = true;
                userAgreementCheckBox.onchange = function () {
                    confirmPlanButton.disabled = !this.checked;
                };
            }
        };

        return self;
    };


    $(function () {
        var confirmPlan = confirmPlanModel(
            initialPageData.get('is_upgrade'),
            initialPageData.get('current_plan'),
            initialPageData.get('new_plan')
        );

        $('#confirm-plan').koApplyBindings(confirmPlanModel);
        $('#modal-downgrade').koApplyBindings(confirmPlanModel);

        confirmPlan.init();
    });
});
