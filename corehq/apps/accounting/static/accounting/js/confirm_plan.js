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
    var PROJECT_ENDED = "My project ended";
    var FUNDING_ENDED = "The funding for my project ended";
    var CONTINUE_COMMCARE = "I don’t need the features of my paid plan anymore but I plan on continuing using CommCare";
    var SWITCH_TOOLS = "We are switching to a different mobile data collection tool";
    var BUDGET_REASONS = "For budget reasons";
    var LIMITED_FEATURES = "I need more limited features";
    var MORE_FEATURES = "I need additional/custom features";
    var OTHER = "Other";

    var confirmPlanModel = function (isUpgrade, currentPlan, newPlan) {
        'use strict';
        var self = {};

        self.isUpgrade = isUpgrade;
        self.currentPlan = currentPlan;
        self.newPlan = newPlan;

        // If the user is upgrading, don't let them continue until they agree to the minimum subscription terms
        self.userAgreementSigned = ko.observable(!isUpgrade);

        self.downgradeReasonList = ko.observableArray([
            PROJECT_ENDED,
            FUNDING_ENDED,
            CONTINUE_COMMCARE,
            SWITCH_TOOLS,
        ]);
        self.newToolReasonList = ko.observableArray([
            BUDGET_REASONS,
            LIMITED_FEATURES,
            MORE_FEATURES,
            OTHER,
        ]);

        self.downgradeReason = ko.observable("");
        self.newTool = ko.observable("");
        self.newToolReason = ko.observable("");
        self.otherNewToolReason = ko.observable("");
        self.requiredQuestionsAnswered = ko.observable(false);

        self.projectEnded = ko.computed(function () {
            return self.downgradeReason() === PROJECT_ENDED;
        });
        self.newToolNeeded = ko.computed(function () {
            return self.downgradeReason() === SWITCH_TOOLS;
        });
        self.otherSelected = ko.computed(function () {
            return self.newToolReason() === OTHER;
        });
        self.requiredQuestionsAnswered = ko.computed(function () {
            if (self.downgradeReason() == null) {
                return false;
            }
            var newToolNeeded =
                self.downgradeReason() === SWITCH_TOOLS;
            var newToolAnswered = self.newTool() !== "";
            var newToolReasonAnswered = (self.newToolReason() !== "" && self.newToolReason() !== OTHER) ||
                (self.newToolReason() === OTHER && self.otherNewToolReason() !== "");

            return (self.downgradeReason() !== "" && !newToolNeeded) ||
                (newToolNeeded && newToolAnswered && newToolReasonAnswered);
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
                if (self.otherSelected()) {
                    document.getElementById("new-tool-reason").value = document.getElementById("text-tool-reason").value;
                } else {
                    document.getElementById("new-tool-reason").value = $("#select-tool-reason").val().join(", ");
                }

                document.getElementById("downgrade-reason").value = $("#select-downgrade-reason").val().join(", ");
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
