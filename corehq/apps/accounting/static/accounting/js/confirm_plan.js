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

        // If the user is upgrading, don't let them continue until they agree to the minimum subscription terms
        self.userAgreementSigned = ko.observable(!isUpgrade);



        self.downgradeReasonList = ko.observableArray([
            "My project ended",
            "The funding for my project ended",
            "I don’t need the features of my paid plan anymore but I plan on continuing using CommCare",
            "We are switching to a different mobile data collection tool",
        ]);
        self.newToolReasonList = ko.observableArray([
            "For budget reason",
            "I need more limited features",
            "I need additional/custom features",
            "Other",
        ]);
        self.downgradeReason = ko.observable("");
        self.newToolReason = ko.observable("");
        self.projectEnded = ko.computed(function () {
            return self.downgradeReason() === "My project ended";
        });
        self.newToolNeeded = ko.computed(function () {
            return self.downgradeReason() === "We are switching to a different mobile data collection tool";
        });
        self.otherSelected = ko.computed(function () {
            return self.newToolReason() === "Other";
        });

        self.form = undefined;
        self.openDowngradeModal = function (confirmPlanModel, e) {
            self.form = $(e.currentTarget).closest("form");
            if (confirmPlanModel.isUpgrade) {
                self.form.submit();
            } else {
                var $modal = $("#modal-downgrade");
                $modal.modal('show');
            }
        };
        self.submitDowngrade = function (pricingTable, e) {
            var finish = function () {
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

        return self;
    };


    $(function () {
        var confirmPlan = confirmPlanModel(
            initialPageData.get('is_upgrade'),
            initialPageData.get('current_plan'),
            initialPageData.get('new_plan_name')
        );

        $('#confirm-plan-content').koApplyBindings(confirmPlan);
        $('#modal-downgrade').koApplyBindings(confirmPlan);
    });
});
