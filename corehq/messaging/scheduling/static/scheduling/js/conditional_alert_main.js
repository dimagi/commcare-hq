hqDefine(
    "scheduling/js/conditional_alert_main",
    [
        "jquery",
        "knockout",
        "underscore",
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

        function getFormContents() {
            return _.object(
                _.map($(".main-form").serializeArray(), function (obj) {
                    return [obj.name, obj.value];
                })
            );
        }

        $(function () {
            var name = initialPageData.get("rule_name");
            var basicInformation = basicInformationTab(name);
            // setup tab
            basicInformation.setRuleTabVisibility();
            $("#conditional-alert-basic-info-panel").koApplyBindings(
                basicInformation
            );

            var initialFormContent = getFormContents();

            $(".main-form").on("submit", function () {
                var finalFormContent = getFormContents();
                // compare changes with initialFormContent to check if only 'message' has changed
                var formContentChanges = [];
                Object.keys(finalFormContent).forEach(function (key) {
                    finalFormContent[key] !== initialFormContent[key]
                        ? formContentChanges.push(key)
                        : null;
                });
                var runMessagingRule = !_.isEqual(
                    ["message"],
                    formContentChanges
                );
                // to convey to HQ to reprocess or not
                var input = $("<input />")
                    .attr("type", "hidden")
                    .attr("name", "runMessagingRule")
                    .attr("value", runMessagingRule.toString());
                $(this).append(input);
                return true;
            });
        });
    }
);
