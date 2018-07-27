hqDefine("accounting/js/enterprise_settings", [
    'jquery',
    'knockout',
    'hqwebapp/js/initial_page_data',
], function(
    $,
    ko,
    initialPageData
) {
    var settingsFormModel = function(restrictSignup) {
        var self = {};
        self.restrictSignup = ko.observable(restrictSignup);
        return self;
    };

    $(function() {
        var form = settingsFormModel(initialPageData.get('restrict_signup'));
        $('#enterprise-settings-form').koApplyBindings(form);
    });
});
