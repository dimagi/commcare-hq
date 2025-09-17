import "commcarehq";
import $ from "jquery";
import _ from "underscore";
import ko from "knockout";
import assertProperties from "hqwebapp/js/assert_properties";
import initialPageData from "hqwebapp/js/initial_page_data";
import "hqwebapp/js/components/search_box";

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
