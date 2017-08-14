var url = hqImport('hqwebapp/js/initial_page_data.js').reverse;

window.angular.module('icdsApp').factory('progressReportService', ['$http', function($http) {
    return {
        getData: function(params) {
            var get_url = url('progress_report', '---');
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);
