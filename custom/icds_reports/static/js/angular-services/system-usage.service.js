window.angular.module('icdsApp').factory('systemUsageService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    return {
        getAwcOpenedData: function (step, params) {
            gtag.event('System Usage Service', 'Fetching data started', 'getAwcOpenedData');
            var get_url = url('awc_opened', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('System Usage Service', 'Fetching data succeeded', 'getAwcOpenedData');
                    return response;
                },
                function () {
                    gtag.event('System Usage Service', 'Fetching data failed', 'getAwcOpenedData');
                }
            );
        },
    };
}]);
