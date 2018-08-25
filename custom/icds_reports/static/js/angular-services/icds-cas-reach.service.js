var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('icdsCasReachService', ['$http', function($http) {
    return {
        getAwcDailyStatusData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'ICDS CAS Reach Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Awc Daily Status',
            });
            var get_url = url('awc_daily_status', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'ICDS CAS Reach Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Awc Daily Status',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'ICDS CAS Reach Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Awc Daily Status',
                    });
                }
            );
        },
        getAwcsCoveredData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'ICDS CAS Reach Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Awcs Covered',
            });
            var get_url = url('awcs_covered', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'ICDS CAS Reach Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Awcs Covered',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'ICDS CAS Reach Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Awcs Covered',
                    });
                }
            );
        },
    };
}]);
