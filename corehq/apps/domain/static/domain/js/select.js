hqDefine("domain/js/select", [
    'jquery',
    'underscore',
    'knockout',
    'hqwebapp/js/assert_properties',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/components.ko',    // search box
], function (
    $,
    _,
    ko,
    assertProperties,
    initialPageData
) {
    var searchModel = function (options) {
        assertProperties.assert(options, ['domainLinks', 'invitationLinks']);
        var self = {};

        self.allDomainLinks = ko.observableArray(options.domainLinks);
        self.invitationLinks = ko.observableArray(options.invitationLinks);
        self.domainLinks = ko.observableArray();

        self.query = ko.observable('');

        self._match = function (link) {
            return link.display_name.toLowerCase().indexOf(self.query().toLowerCase()) !== -1;
        };
        self.search = function () {
            self.domainLinks(_.filter(self.allDomainLinks(), self._match));
        };

        self.search();

        return self;
    };

    $(function () {
        $("#all-links").koApplyBindings(searchModel({
            domainLinks: initialPageData.get('domain_links'),
            invitationLinks: initialPageData.get('invitation_links'),
        }));
    });
});
