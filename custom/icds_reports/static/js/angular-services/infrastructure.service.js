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
        getFunctionalToiletData: function(step, params) {
            var get_url = url('functional_toilet', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getMedicineKitData: function(step, params) {
            var get_url = url('medicine_kit', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getInfantsWeightScaleData: function(step, params) {
            var get_url = url('infants_weight_scale', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);