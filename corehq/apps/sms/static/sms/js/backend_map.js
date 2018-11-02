hqDefine('sms/js/backend_map',[
    "underscore",
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
], function (_, $, ko, initialPageData) {
    function BackendMapping(prefix, backendId) {
        'use strict';
        var self = {};
        self.prefix = ko.observable(prefix);
        self.backend_id = ko.observable(backendId);
        return self;
    }

    function BackendMapViewModel(initial) {
        'use strict';
        var self = {};

        self.backend_map = ko.observableArray();

        _.map(
            initial.backend_map,
            function (mapping) {
                self.backend_map.push(BackendMapping(mapping.prefix, mapping.backend_id));
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
            self.backend_map.push(BackendMapping('', ''));
        };

        self.removeMapping = function () {
            self.backend_map.remove(this);
        };
        return self;
    }

    $(function () {
        var backendViewModel = BackendMapViewModel({
            'backend_map': initialPageData.get('form.backend_map'),
        });
        $('#backend-map-form').koApplyBindings(backendViewModel);
    });
});
