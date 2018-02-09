var url = hqImport('hqwebapp/js/initial_page_data').reverse;

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
        getPrevalenceOfStuntingData: function(step, params) {
            var get_url = url('prevalence_of_stunting', step);
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
        getChildrenInitiatedData: function(step, params) {
            var get_url = url('children_initiated', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getInstitutionalDeliveriesData: function(step, params) {
            var get_url = url('institutional_deliveries', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getImmunizationCoverageData: function(step, params) {
            var get_url = url('immunization_coverage', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);
