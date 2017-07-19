var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').factory('maternalChildService', ['$http', function($http) {
    return {
        getUnderweightChildrenData: function(step, params) {
            var get_url = url('underweight_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getPrevalenceOfSevereData: function(step, params) {
            var get_url = url('prevalence_of_severe', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getPrevalenceOfStunningData: function(step, params) {
            var get_url = url('prevalence_of_stunning', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);