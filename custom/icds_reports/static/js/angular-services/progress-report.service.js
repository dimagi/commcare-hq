var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var progressReportServiceEventCategory = google.trackCategory('Progress Report Service');

window.angular.module('icdsApp').factory('progressReportService', ['$http', function($http) {
    return {
        getData: function(params) {
            progressReportServiceEventCategory.event(
                'Fetching data started', 'getData', {'params': params}
            );
            var get_url = url('fact_sheets', '---');
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    progressReportServiceEventCategory.event(
                        'Fetching data succeeded', 'getData', {'params': params}
                    );
                    return response;
                },
                function() {
                    progressReportServiceEventCategory.event(
                        'Fetching data failed', 'getData', {'params': params}
                    );
                }
            );
        },
    };
}]);
