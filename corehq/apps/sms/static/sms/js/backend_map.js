import "commcarehq";
import _ from "underscore";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";

function backendMapping(prefix, backendId) {
    var self = {};
    self.prefix = ko.observable(prefix);
    self.backend_id = ko.observable(backendId);
    return self;
}

function backendMapViewModel(initial) {
    var self = {};

    self.backend_map = ko.observableArray();

    _.map(
        initial.backend_map,
        function (mapping) {
            self.backend_map.push(backendMapping(mapping.prefix, mapping.backend_id));
        }
    );

    self.backend_map_json = ko.computed(function () {
        return JSON.stringify(
            _.map(
                self.backend_map(),
                function (mapping) {
                    return {'prefix': mapping.prefix(), 'backend_id': mapping.backend_id()};
                }
            )
        );
    });

    self.addMapping = function () {
        self.backend_map.push(backendMapping('', ''));
    };

    self.removeMapping = function () {
        self.backend_map.remove(this);
    };
    return self;
}

$(function () {
    var backendViewModel = backendMapViewModel({
        'backend_map': initialPageData.get('form.backend_map'),
    });
    $('#backend-map-form').koApplyBindings(backendViewModel);
});
