var url = hqImport('hqwebapp/js/initial_page_data.js').reverse;

window.angular.module('icdsApp').factory('icdsCasReachService', ['$http', function($http) {
    return {
        getAwcDailyStatusData: function(step, params) {
            var get_url = url('awc_daily_status', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getAwcsCoveredData: function(step, params) {
            var get_url = url('awcs_covered', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);
