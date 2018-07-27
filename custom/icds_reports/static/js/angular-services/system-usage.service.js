var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var systemUsageServiceEventCategory = google.trackCategory('System Usage Service');

window.angular.module('icdsApp').factory('systemUsageService', ['$http', function($http) {
    return {
        getAwcOpenedData: function(step, params) {
            systemUsageServiceEventCategory.event(
                'Fetching data started', 'getAwcOpenedData', {'step': step, 'params': params}
            );
            var get_url = url('awc_opened', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    systemUsageServiceEventCategory.event(
                        'Fetching data succeeded', 'getAwcOpenedData', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    systemUsageServiceEventCategory.event(
                        'Fetching data failed', 'getAwcOpenedData', {'step': step, 'params': params}
                    );
                },
            );
        },
    };
}]);
