hqDefine("domain/js/manage_alerts",[
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function ($, ko, _, initialPageData) {

    var domainAlert = function (options) {
        var self = ko.mapping.fromJS(options);
        self.editUrl = initialPageData.reverse('domain_edit_alert', self.id());
        return self;
    };

    $(function () {
        $('#ko-alert-container').koApplyBindings({
            'alerts': _.map(initialPageData.get('alerts'), domainAlert),
        });
    });
});
