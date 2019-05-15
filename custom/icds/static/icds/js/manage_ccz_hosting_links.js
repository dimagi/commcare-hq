hqDefine('icds/js/manage_ccz_hosting_links', [
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
        var cczHostingLink = function (id, identifier) {
            var self = {};
            self.identifier = identifier;
            self.editUrl = initialPageData.reverse("edit_ccz_hosting_link", id);
            self.pageUrl = initialPageData.reverse("ccz_hosting", identifier);
            return self;
        };
        var links = initialPageData.get("links");
        if ($("#links").length) {
            $("#links").koApplyBindings({
                'links': _.map(links, function (link) { return cczHostingLink(link.id, link.identifier); }),
            });
        }
    });
});