var url = hqImport('hqwebapp/js/urllib').reverse;

window.angular.module('icdsApp').factory('systemUsageService', ['$http', function($http) {
    return {
        getAwcOpenedData: function(step, params) {
            var get_url = url('awc_opened', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);
