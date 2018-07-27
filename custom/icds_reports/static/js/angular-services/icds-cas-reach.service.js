var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var icdsCasReachServiceEventCategory = google.trackCategory('ICDS CAS Reach Service');

window.angular.module('icdsApp').factory('icdsCasReachService', ['$http', function($http) {
    return {
        getAwcDailyStatusData: function(step, params) {
            icdsCasReachServiceEventCategory.event(
                'Fetching data started', 'Awc Daily Status', {'step': step, 'params': params}
            );
            var get_url = url('awc_daily_status', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    icdsCasReachServiceEventCategory.event(
                        'Fetching data succeeded', 'Awc Daily Status', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    icdsCasReachServiceEventCategory.event(
                        'Fetching data failed', 'Awc Daily Status', {'step': step, 'params': params}
                    );
                },
            );
        },
        getAwcsCoveredData: function(step, params) {
            icdsCasReachServiceEventCategory.event(
                'Fetching data started', 'Awcs Covered', {'step': step, 'params': params}
            );
            var get_url = url('awcs_covered', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    icdsCasReachServiceEventCategory.event(
                        'Fetching data succeeded', 'Awcs Covered', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    icdsCasReachServiceEventCategory.event(
                        'Fetching data failed', 'Awcs Covered', {'step': step, 'params': params}
                    );
                },
            );
        },
    };
}]);
