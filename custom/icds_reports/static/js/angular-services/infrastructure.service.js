var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var infrastuctureServiceEventCategory = google.trackCategory('Infrastructure Service');

window.angular.module('icdsApp').factory('infrastructureService', ['$http', function($http) {
    return {
        getCleanWaterData: function(step, params) {
            infrastuctureServiceEventCategory.event(
                'Fetching data started', 'Clean Water', [step, params]
            );
            var get_url = url('clean_water', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data succeeded', 'Clean Water', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data failed', 'Clean Water', {'step': step, 'params': params}
                    );
                }
            );
        },
        getFunctionalToiletData: function(step, params) {
            infrastuctureServiceEventCategory.event(
                'Fetching data started', 'Functional Toilet', [step, params]
            );
            var get_url = url('functional_toilet', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data succeeded', 'Functional Toilet', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data failed', 'Functional Toilet', {'step': step, 'params': params}
                    );
                }
            );
        },
        getMedicineKitData: function(step, params) {
            infrastuctureServiceEventCategory.event(
                'Fetching data started', 'Medicine Kit', [step, params]
            );
            var get_url = url('medicine_kit', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data succeeded', 'Medicine Kit', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data failed', 'Medicine Kit', {'step': step, 'params': params}
                    );
                }
            );
        },
        getInfantsWeightScaleData: function(step, params) {
            infrastuctureServiceEventCategory.event(
                'Fetching data started', 'Infants Weight Scale', [step, params]
            );
            var get_url = url('infants_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data succeeded', 'Infants Weight Scale', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data failed', 'Infants Weight Scale', {'step': step, 'params': params}
                    );
                }
            );
        },
        getAdultWeightScaleData: function(step, params) {
            infrastuctureServiceEventCategory.event(
                'Fetching data started', 'Adult Weight Scale', [step, params]
            );
            var get_url = url('adult_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data succeeded', 'Adult Weight Scale', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    infrastuctureServiceEventCategory.event(
                        'Fetching data failed', 'Adult Weight Scale', {'step': step, 'params': params}
                    );
                }
            );
        },
    };
}]);
