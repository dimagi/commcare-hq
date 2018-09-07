var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('progressReportService', ['$http', function($http) {
    return {
        getData: function(params) {
            window.ga('send', 'event', {
                'eventCategory': 'Progress Report Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getData',
            });
            var get_url = url('fact_sheets', '---');
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Progress Report Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getData',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Progress Report Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getData',
                    });
                }
            );
        },
    };
}]);
