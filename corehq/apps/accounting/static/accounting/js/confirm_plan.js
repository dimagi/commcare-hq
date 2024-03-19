"use strict";
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

    var confirmPlanModel = function (isUpgrade, isSameEdition, isPaused, currentPlan) {
        var self = {};

        self.isUpgrade = isUpgrade;
        self.isSameEdition = isSameEdition;
        self.isPaused = isPaused;
        self.currentPlan = currentPlan;

        // If the user is upgrading, don't let them continue until they agree to the minimum subscription terms
        self.oUserAgreementSigned = ko.observable(!isUpgrade || isSameEdition);

        self.downgradeReasonList = [
            PROJECT_ENDED,
            FUNDING_ENDED,
            SWITCH_TOOLS,
        ];

        if (!self.isPaused) {
            self.downgradeReasonList.push(CONTINUE_COMMCARE);
        }

        self.newToolReasonList = [
            BUDGET_REASONS,
            LIMITED_FEATURES,
            MORE_FEATURES,
            OTHER,
        ];

        self.oDowngradeReason = ko.observableArray();
        self.oNewTool = ko.observable("");
        self.oNewToolReason = ko.observableArray();
        self.oOtherNewToolReason = ko.observable("");
        self.oWillProjectRestart = ko.observable("");
        self.oFeedback = ko.observable("");

        self.oProjectEnded = ko.computed(function () {
            return _.contains(self.oDowngradeReason(), PROJECT_ENDED);
        });
        self.oNewToolNeeded = ko.computed(function () {
            return _.contains(self.oDowngradeReason(), SWITCH_TOOLS);
        });
        self.oOtherSelected = ko.computed(function () {
            return _.contains(self.oNewToolReason(), OTHER);
        });
        self.oRequiredQuestionsAnswered = ko.computed(function () {
            if (_.isEmpty(self.oDowngradeReason())) {
                return false;
            }
            var newToolNeeded = _.contains(self.oDowngradeReason(), SWITCH_TOOLS),
                newToolAnswered = self.oNewTool() !== "",
                newToolReasonAnswered = (!_.isEmpty(self.oNewToolReason()) && !_.contains(self.oNewToolReason(), OTHER))
                    || (!_.isEmpty(self.oOtherNewToolReason()) && _.contains(self.oNewToolReason(), OTHER));

            return (self.oDowngradeReason() && !newToolNeeded) || (newToolNeeded && newToolAnswered && newToolReasonAnswered);
        });

        self.form = undefined;
        self.openDowngradeModal = function (confirmPlanModel, e) {
            self.form = $(e.currentTarget).closest("form");
            if (confirmPlanModel.isUpgrade || confirmPlanModel.isSameEdition) {
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
                var newToolReason = self.oNewToolReason().join(", ");
                if (self.oOtherSelected()) {
                    newToolReason = newToolReason + ': "' + self.oOtherNewToolReason() + '"';
                }
                $('#new-tool').val(self.oNewTool());
                $("#new-tool-reason").val(newToolReason);

                $('#downgrade-reason').val(self.oDowngradeReason().join(", "));
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
            initialPageData.get('is_same_edition'),
            initialPageData.get('is_paused'),
            initialPageData.get('current_plan')
        );

        $('#confirm-plan-content').koApplyBindings(confirmPlan);
        $('#modal-downgrade').koApplyBindings(confirmPlan);
    });
});
