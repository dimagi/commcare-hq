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
    function ($, ko, _, initialPageData) {
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
                var shouldInitiateRule = _.find(_.keys(finalFormContent), function (key) {
                    if (finalFormContent[key] !== initialFormContent[key] && key !== "content-message") {
                        return true;
                    }
                });
                $("#initiate_rule").val(Boolean(shouldInitiateRule));

                return true;
            });
        });
    }
);
