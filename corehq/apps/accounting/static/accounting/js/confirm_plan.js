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
    var PROJECT_ENDED = gettext("My project ended");
    var FUNDING_ENDED = gettext("The funding for my project ended");
    var CONTINUE_COMMCARE = gettext("I don’t need the features of my paid plan anymore but I plan on continuing using CommCare");
    var SWITCH_TOOLS = gettext("We are switching to a different mobile data collection tool");
    var BUDGET_REASONS = gettext("For budget reasons");
    var LIMITED_FEATURES = gettext("I need more limited features");
    var MORE_FEATURES = gettext("I need additional/custom features");
    var OTHER = gettext("Other");

    var confirmPlanModel = function (isUpgrade, currentPlan) {
        'use strict';
        var self = {};

        self.isUpgrade = isUpgrade;
        self.currentPlan = currentPlan;

        // If the user is upgrading, don't let them continue until they agree to the minimum subscription terms
        self.userAgreementSigned = ko.observable(!isUpgrade);

        self.downgradeReasonList = [
            PROJECT_ENDED,
            FUNDING_ENDED,
            CONTINUE_COMMCARE,
            SWITCH_TOOLS,
        ];
        self.newToolReasonList = [
            BUDGET_REASONS,
            LIMITED_FEATURES,
            MORE_FEATURES,
            OTHER,
        ];

        self.downgradeReason = ko.observableArray();
        self.newTool = ko.observable("");
        self.newToolReason = ko.observableArray();
        self.otherNewToolReason = ko.observable("");
        self.oWillProjectRestart = ko.observable("");
        self.oFeedback = ko.observable("");
        self.requiredQuestionsAnswered = ko.observable(false);

        self.projectEnded = ko.computed(function () {
            return _.contains(self.downgradeReason(), PROJECT_ENDED);
        });
        self.newToolNeeded = ko.computed(function () {
            return _.contains(self.downgradeReason(), SWITCH_TOOLS);
        });
        self.otherSelected = ko.computed(function () {
            return _.contains(self.newToolReason(), OTHER);
        });
        self.requiredQuestionsAnswered = ko.computed(function () {
            if (!self.downgradeReason()) {
                return false;
            }
            var newToolNeeded = _.contains(self.downgradeReason(), SWITCH_TOOLS),
                newToolAnswered = self.newTool() !== "",
                newToolReasonAnswered = (self.newToolReason() && !_.contains(self.newToolReason(), OTHER))
                    || (self.otherNewToolReason() && _.contains(self.newToolReason(), OTHER));

            return (self.downgradeReason() && !newToolNeeded) || (newToolNeeded && newToolAnswered && newToolReasonAnswered);
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
                var newToolReason = self.newToolReason().join(", ");
                if (self.otherSelected()) {
                    newToolReason = newToolReason + ': "' + self.otherNewToolReason() + '"';
                }
                $('#new-tool').val(self.newTool());
                $("#new-tool-reason").val(newToolReason);

                $('#downgrade-reason').val(self.downgradeReason().join(", "));
                $('#will-project-restart').val(self.oWillProjectRestart());
                $('#feedback').val(self.oFeedback());

                self.form.submit();
            }
        };

        return self;
    };


    $(function () {
        var confirmPlan = confirmPlanModel(
            initialPageData.get('is_upgrade'),
            initialPageData.get('current_plan')
        );

        $('#confirm-plan-content').koApplyBindings(confirmPlan);
        $('#modal-downgrade').koApplyBindings(confirmPlan);
    });
});
