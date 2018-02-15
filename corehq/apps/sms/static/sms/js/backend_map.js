hqDefine('sms/js/backend_map', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    function BackendMapping(prefix, backend_id) {
        'use strict';
        var self = this;
        self.prefix = ko.observable(prefix);
        self.backend_id = ko.observable(backend_id);
    }

    function BackendMapViewModel(initial) {
        'use strict';
        var self = this;

        self.backend_map = ko.observableArray();

        _.map(
            initial.backend_map,
            function(mapping) {
                self.backend_map.push(new BackendMapping(mapping.prefix, mapping.backend_id));
            }
        );

        self.backend_map_json = ko.computed(function() {
            return JSON.stringify(
                _.map(
                    self.backend_map(),
                    function(mapping) {
                        return {'prefix': mapping.prefix(), 'backend_id': mapping.backend_id()};
                    }
                )
            );
        });

        self.addMapping = function() {
            self.backend_map.push(new BackendMapping('', ''));
        };

        self.removeMapping = function() {
            self.backend_map.remove(this);
        };
    }

    $(function(){
        var backendViewModel = new BackendMapViewModel({
            'backend_map': initialPageData.get('form.backend_map')
        });
        $('#backend-map-form').koApplyBindings(backendViewModel);
    });
});
