hqDefine("scheduling/js/conditional_alert_main", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/initial_page_data',
    'data_interfaces/js/case_rule_criteria',
    'data_interfaces/js/case_property_input',
    'hqwebapp/js/bootstrap3/widgets',
    'scheduling/js/create_schedule.ko',
    'data_interfaces/js/make_read_only',
    'commcarehq',
    // maybe these should go in hqwebapp/js/ckeditor_knockout_bindings...but this page doesn't depend on that?
    'ckeditor5/build/ckeditor5-dll',
    '@ckeditor/ckeditor5-editor-classic/build/editor-classic',
    '@ckeditor/ckeditor5-autoformat/build/autoformat',
    '@ckeditor/ckeditor5-basic-styles/build/basic-styles',
    '@ckeditor/ckeditor5-block-quote/build/block-quote',
    '@ckeditor/ckeditor5-essentials/build/essentials',
    '@ckeditor/ckeditor5-font/build/font',
    '@ckeditor/ckeditor5-heading/build/heading',
    '@ckeditor/ckeditor5-html-support/build/html-support',
    '@ckeditor/ckeditor5-horizontal-line/build/horizontal-line',
    '@ckeditor/ckeditor5-image/build/image',
    '@ckeditor/ckeditor5-indent/build/indent',
    '@ckeditor/ckeditor5-link',
    '@ckeditor/ckeditor5-list',
    '@ckeditor/ckeditor5-paste-from-office',
    '@ckeditor/ckeditor5-restricted-editing',
    '@ckeditor/ckeditor5-alignment',
], function (
    $,
    _,
    ko,
    initialPageData,
    CaseRuleCriteria,
    casePropertyInput
) {
    function BasicInformationTab(name) {
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
        self.setRuleTabVisibility();
        return self;
    }

    $(function () {
        casePropertyInput.register();

        $("#conditional-alert-basic-info-panel").koApplyBindings(BasicInformationTab(
            initialPageData.get('rule_name')
        ));

        $('#rule-criteria-panel').koApplyBindings(CaseRuleCriteria(
            initialPageData.get('criteria_initial'),
            initialPageData.get('criteria_constants')
        ));
    });
});
