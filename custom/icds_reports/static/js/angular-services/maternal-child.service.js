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
        getNewbornLowBirthData: function(step, params) {
            var get_url = url('low_birth', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        earlyInitiationBreastfeeding: function(step, params) {
            var get_url = url('early_initiation', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getExclusiveBreastfeedingData: function(step, params) {
            var get_url = url('exclusive-breastfeeding', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);