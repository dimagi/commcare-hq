window.angular.module('icdsApp').factory('progressReportService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    return {
        getData: function (params) {
            gtag.event('Progress Report Service', 'Fetching data started', 'getData');
            var get_url = url('fact_sheets', '---');
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Progress Report Service', 'Fetching data succeeded', 'getData');
                    return response;
                },
                function () {
                    gtag.event('Progress Report Service', 'Fetching data failed', 'getData');
                }
            );
        },
    };
}]);
