var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('systemUsageService', ['$http', function($http) {
    return {
        getAwcOpenedData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'System Usage Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getAwcOpenedData',
            });
            var get_url = url('awc_opened', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'System Usage Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getAwcOpenedData',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'System Usage Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getAwcOpenedData',
                    });
                }
            );
        },
    };
}]);
