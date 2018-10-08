var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var gtag = hqImport('analytix/js/google').track;

window.angular.module('icdsApp').factory('icdsCasReachService', ['$http', function($http) {
    return {
        getAwcDailyStatusData: function(step, params) {
            gtag.event('ICDS CAS Reach Service', 'Fetching data started', 'Awc Daily Status');
            var get_url = url('awc_daily_status', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('ICDS CAS Reach Service', 'Fetching data succeeded', 'Awc Daily Status');
                    return response;
                },
                function() {
                    gtag.event('ICDS CAS Reach Service', 'Fetching data failed', 'Awc Daily Status');
                }
            );
        },
        getAwcsCoveredData: function(step, params) {
            gtag.event('ICDS CAS Reach Service', 'Fetching data started', 'Awcs Covered');
            var get_url = url('awcs_covered', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    gtag.event('ICDS CAS Reach Service', 'Fetching data succeeded', 'Awcs Covered');
                    return response;
                },
                function() {
                    gtag.event('ICDS CAS Reach Service', 'Fetching data failed', 'Awcs Covered');
                }
            );
        },
    };
}]);
