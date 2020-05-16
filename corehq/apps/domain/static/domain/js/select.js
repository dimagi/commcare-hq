hqDefine("domain/js/select", [
    'jquery',
    'knockout',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/components.ko',    // search box
], function (
    $,
    ko,
    assertProperties,
    initialPageData
) {
    var searchModel = function (options) {
        assertProperties.assert(options, ['domainLinks', 'invitationLinks'])
        var self = {};

        self.invitationLinks = ko.observableArray(options.invitationLinks);
        self.domainLinks = ko.observableArray(options.domainLinks);

        return self;
    };

    $(function () {
        $("#all-links").koApplyBindings(searchModel({
            domainLinks: initialPageData.get('domain_links'),
            invitationLinks: initialPageData.get('invitation_links'),
        }));
    });
});
