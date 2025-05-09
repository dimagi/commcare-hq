import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";

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
