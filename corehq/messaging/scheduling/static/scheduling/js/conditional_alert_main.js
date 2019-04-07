hqDefine("scheduling/js/conditional_alert_main", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_rule_criteria',
    'scheduling/js/create_schedule.ko',
    'data_interfaces/js/make_read_only',
], function ($, ko, initialPageData) {
    function conditionalAlertValidations (formSubmitted) {
        var self = {};
        self.newForm = !formSubmitted;
        self.basicTabValid = function () {
            var name = $("#id_conditional-alert-name").val().trim();
            return !_.isEmpty(name);
        };
        self.ruleTabValid = function () {
            var ruleCaseType = $("#id_criteria-case_type").val();
            return !_.isEmpty(ruleCaseType);
        };
        self.showRequiredErrorMessage = function () {
            $("#required_error_message").removeClass('hidden');
        };
        self.hideRequiredErrorMessage = function () {
            $("#required_error_message").addClass('hidden');
        };
        self.validateBasicTab = function () {
            var isValid = self.basicTabValid();
            if (!isValid) {
                self.showRequiredErrorMessage();
                if (self.newForm) {
                    $("#rule-nav").addClass("hidden");
                    $("#schedule-nav").addClass("hidden");
                }
            } else {
                self.hideRequiredErrorMessage();
                $("#rule-nav").removeClass("hidden");
            }
            return isValid;
        };
        self.validateRuleTab = function () {
            var isValid = self.ruleTabValid();
            if (!isValid) {
                self.showRequiredErrorMessage();
                if (self.newForm) {
                    $("#schedule-nav").addClass("hidden");
                }
            } else {
                self.hideRequiredErrorMessage();
                $("#schedule-nav").removeClass("hidden");
            }
            return isValid;
        };
        self.navigateToNav = function (navId) {
            $(navId).find('a').trigger('click');
        };
        self.handleBasicNavContinue = function () {
            if (self.validateBasicTab()) {
                self.navigateToNav('#rule-nav');
            }
        };
        self.handleRuleNavContinue = function () {
            if (self.validateRuleTab()) {
                self.navigateToNav('#schedule-nav');
            }
        };
        return self;
    };

    $(function () {
        var formSubmitted = initialPageData.get('form_submitted');
        var validationModel = conditionalAlertValidations(formSubmitted);
        if (formSubmitted) {
            // set up tabs
            validationModel.validateBasicTab();
            validationModel.validateRuleTab();
        }
        // bind for validation
        $("#basic_continue").koApplyBindings(validationModel);
        $("#rule_continue").koApplyBindings(validationModel);
    });
});
