hqDefine(
    "scheduling/js/conditional_alert_main",
    [
        "jquery",
        "knockout",
        "hqwebapp/js/initial_page_data",
        "hqwebapp/js/widgets",
        "data_interfaces/js/case_rule_criteria",
        "scheduling/js/create_schedule.ko",
        "data_interfaces/js/make_read_only",
    ],
    function ($, ko, initialPageData) {
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
                $(navId).find("a").trigger("click");
            };
            self.handleBasicNavContinue = function () {
                $("#rule-nav").removeClass("hidden");
                $("#rule-nav").find("a").trigger("click");
            };
            return self;
        }

        $(function () {
            var name = initialPageData.get("rule_name");
            var basicInformation = basicInformationTab(name);
            // setup tab
            basicInformation.setRuleTabVisibility();
            $("#conditional-alert-basic-info-panel").koApplyBindings(
                basicInformation
            );

            $("#conditional-alert-save-btn").click(function () {
                if (!name) {
                    $("#conditional-alert-form").submit();
                } else {
                    var caseType = $("#id_criteria-case_type").val();
                    var caseCountUrl = initialPageData.reverse(
                        "count_cases_by_case_type"
                    );
                    $("#conditional-alert-save-btn").html(
                        '<i class="fa fa-spin fa-spinner"></i>'
                    );
                    $.ajax({
                        type: "GET",
                        url: caseCountUrl,
                        data: { case_type: caseType },
                        success: function (data) {
                            $("#case-count").text(data.case_count);
                            $("#conditional-alert-warning-modal").modal("show");
                            $("#conditional-alert-save-btn").text("Save");
                        },
                        error: function (data) {
                            $("#conditional-alert-save-btn").text(
                                data.responseJSON.error
                            );
                        },
                    });

                    $("#conditional-alert-yes-btn").click(function () {
                        $("#conditional-alert-form").submit();
                    });
                }
            });
        });
    }
);
