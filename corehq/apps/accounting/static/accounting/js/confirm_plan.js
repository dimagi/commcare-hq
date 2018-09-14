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
            var $button = $(e.currentTarget);
            $button.disableButton();
            if (self.form) {
                var downgradeReason = "";
                var selectedDowngradeOptions = document.getElementById("select-downgrade-reason").selectedOptions;
                for (var i = 0; i < selectedDowngradeOptions.length; i++) {
                    downgradeReason += selectedDowngradeOptions[i].value + ", ";
                }
                document.getElementById("downgrade-reason").value = downgradeReason;

                var newToolReason = "";
                var selectedNewToolOptions = document.getElementById("select-tool-reason").selectedOptions;
                for (i = 0; i < selectedNewToolOptions.length; i++) {
                    newToolReason += selectedNewToolOptions[i].value + "\n";
                }
                newToolReason += document.getElementById("text-tool-reason").value;
                document.getElementById("new-tool-reason").value = newToolReason;

                document.getElementById("will-project-restart").value = document.getElementById("select-project-restart").value;
                document.getElementById("new-tool").value = document.getElementById("text-new-tool").value;
                document.getElementById("feedback").value = document.getElementById("text-feedback").value;

                self.form.submit();
            }
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
