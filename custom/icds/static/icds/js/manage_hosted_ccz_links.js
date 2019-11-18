hqDefine('icds/js/manage_hosted_ccz_links', [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
], function (
    $,
    ko,
    _,
    initialPageData
) {
    'use strict';
    $(function () {
        var hostedCCZLink = function (id, identifier) {
            var self = {};
            self.identifier = identifier;
            self.editUrl = initialPageData.reverse("edit_hosted_ccz_link", id);
            self.pageUrl = initialPageData.reverse("hosted_ccz", identifier);
            return self;
        };
        var links = initialPageData.get("links");
        if ($("#links").length) {
            $("#links").koApplyBindings({
                'links': _.map(links, function (link) { return hostedCCZLink(link.id, link.identifier); }),
            });
        }
    });
});
