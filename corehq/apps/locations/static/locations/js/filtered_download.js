import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import "locations/js/widgets";  // location search
import "hqwebapp/js/components/select_toggle";
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";  // slideVisible binding

function FiltersModel(options) {
    var self = {};

    self.location_id = ko.observable();
    self.selected_location_only = ko.observable();
    self.location_status_active = ko.observable();

    self.count = ko.observable(null);
    self.buttonHTML = ko.computed(function () {
        if (self.count() === null) {
            return "<i class='fa fa-spin fa-spinner'></i>";
        }
        var template = self.count() === 1 ? gettext("Download <%- count %> Location") : gettext("Download <%- count %> Locations");
        return _.template(template)({
            count: self.count(),
        });
    });

    self.countLocations = function () {
        self.count(null);
        var data = {
            location_id: self.location_id(),
            selected_location_only: self.selected_location_only(),
            location_status_active: self.location_status_active(),
        };

        $.get({
            url: options.url,
            data: data,
            success: function (data) {
                self.count(data.count);
            },
            error: function () {
                alert(gettext("Error determining number of matching locations"));
            },
        });
    };

    self.location_id.subscribe(self.countLocations);
    self.selected_location_only.subscribe(self.countLocations);
    self.location_status_active.subscribe(self.countLocations);

    return self;
}

$(function () {
    $("#locations-filters").koApplyBindings(FiltersModel({
        'url': initialPageData.get('locations_count_url'),
    }));
});
