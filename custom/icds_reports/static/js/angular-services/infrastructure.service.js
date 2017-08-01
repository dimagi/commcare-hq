var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').factory('infrastructureService', ['$http', function($http) {
    return {
        getCleanWaterData: function(step, params) {
            var get_url = url('clean_water', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);