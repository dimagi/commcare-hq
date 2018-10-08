var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var gtag = hqImport('analytix/js/google').track;

window.angular.module('icdsApp').factory('infrastructureService', ['$http', function($http) {
    return {
        getCleanWaterData: function(step, params) {
            gtag.event('Infrastructure Service', 'Fetching data started', 'Clean Water');
            var get_url = url('clean_water', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('Infrastructure Service', 'Fetching data succeeded', 'Clean Water');
                    return response;
                },
                function() {
                    gtag.event('Infrastructure Service', 'Fetching data failed', 'Clean Water');
                }
            );
        },
        getFunctionalToiletData: function(step, params) {
            gtag.event('Infrastructure Service', 'Fetching data started', 'Functional Toilet');
            var get_url = url('functional_toilet', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('Infrastructure Service', 'Fetching data succeeded', 'Functional Toilet');
                    return response;
                },
                function() {
                    gtag.event('Infrastructure Service', 'Fetching data failed', 'Functional Toilet');
                }
            );
        },
        getMedicineKitData: function(step, params) {
            gtag.event('Infrastructure Service', 'Fetching data started', 'Medicine Kit');
            var get_url = url('medicine_kit', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('Infrastructure Service', 'Fetching data succeeded', 'Medicine Kit');
                    return response;
                },
                function() {
                    gtag.event('Infrastructure Service', 'Fetching data failed', 'Medicine Kit');
                }
            );
        },
        getInfantsWeightScaleData: function(step, params) {
            gtag.event('Infrastructure Service', 'Fetching data started', 'Infants Weight Scale');
            var get_url = url('infants_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('Infrastructure Service', 'Fetching data succeeded', 'Infants Weight Scale');
                    return response;
                },
                function() {
                    gtag.event('Infrastructure Service', 'Fetching data failed', 'Infants Weight Scale');
                }
            );
        },
        getAdultWeightScaleData: function(step, params) {
            gtag.event('Infrastructure Service', 'Fetching data started', 'Adult Weight Scale');
            var get_url = url('adult_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('Infrastructure Service', 'Fetching data succeeded', 'Adult Weight Scale');
                    return response;
                },
                function() {
                    gtag.event('Infrastructure Service', 'Fetching data failed', 'Adult Weight Scale');
                }
            );
        },
    };
}]);
