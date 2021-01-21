hqDefine("scheduling/js/conditional_alert_main", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/widgets',
    'data_interfaces/js/case_rule_criteria',
    'scheduling/js/create_schedule.ko',
    'data_interfaces/js/make_read_only',
], function ($, ko, initialPageData) {
    function basicInformationTab(name) {
        var self = {};
        self.name = ko.observable(name);
        self.basicTabValid = ko.computed(function () {
            return !_.isEmpty(self.name().trim());
        });
        self.setRuleTabVisibility = function () {
            if (self.basicTabValid()) {
                $("#rule-nav").removeClass("hidden");
            }
        };
        self.navigateToNav = function (navId) {
            $(navId).find('a').trigger('click');
        };
        self.handleBasicNavContinue = function () {
            $("#rule-nav").removeClass("hidden");
            $('#rule-nav').find('a').trigger('click');
        };
        return self;
    }

    $(function () {
        var name = initialPageData.get('rule_name');
        var basicInformation = basicInformationTab(name);
        // setup tab
        basicInformation.setRuleTabVisibility();
        $("#conditional-alert-basic-info-panel").koApplyBindings(basicInformation);

        $("#conditional-alert-save-btn").click(function () {
            var newRuleName = $("#id_conditional-alert-name").val();
            if (!name) {
                $("#conditional-alert-form").submit();
            } else if (name !== newRuleName) {
                var caseType = $(
                    "#select2-id_criteria-case_type-container"
                ).text();
                var caseCountUrl = $("#conditional-alert-case-count-url").attr(
                    "url"
                );
                $.ajax({
                    type: "GET",
                    url: caseCountUrl,
                    data: { case_type: caseType },
                    success: function (data) {
                        $("#case-count").text(data["case_count"]);
                    },
                });
                $("#conditional-alert-warning-modal").modal("show");

                $("#conditional-alert-yes-btn").click(function () {
                    $("#conditional-alert-form").submit();
                });
            } else {
                $("#conditional-alert-form").submit();
            }
        });
    });
});
