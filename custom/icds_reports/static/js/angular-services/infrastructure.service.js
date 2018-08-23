var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('infrastructureService', ['$http', function($http) {
    return {
        getCleanWaterData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Infrastructure Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Clean Water',
            });
            var get_url = url('clean_water', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Clean Water',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Clean Water',
                    });
                }
            );
        },
        getFunctionalToiletData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Infrastructure Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Functional Toilet',
            });
            var get_url = url('functional_toilet', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Functional Toilet',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Functional Toilet',
                    });
                }
            );
        },
        getMedicineKitData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Infrastructure Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Medicine Kit',
            });
            var get_url = url('medicine_kit', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Medicine Kit',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Medicine Kit',
                    });
                }
            );
        },
        getInfantsWeightScaleData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Infrastructure Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Infants Weight Scale',
            });
            var get_url = url('infants_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Infants Weight Scale',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Infants Weight Scale',
                    });
                }
            );
        },
        getAdultWeightScaleData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Infrastructure Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Adult Weight Scale',
            });
            var get_url = url('adult_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Adult Weight Scale',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Infrastructure Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Adult Weight Scale',
                    });
                }
            );
        },
    };
}]);
