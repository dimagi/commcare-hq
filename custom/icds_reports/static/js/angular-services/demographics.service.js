var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('demographicsService', ['$http', function($http) {
    return {
        getRegisteredHouseholdData: function(step, params) {
            var get_url = url('registered_household', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getEnrolledChildrenData: function(step, params) {
            var get_url = url('enrolled_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getEnrolledWomenData: function(step, params) {
            var get_url = url('enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getLactatingEnrolledWomenData: function(step, params) {
            var get_url = url('lactating_enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getAdolescentGirlsData: function(step, params) {
            var get_url = url('adolescent_girls', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
        getAdhaarData: function(step, params) {
            var get_url = url('adhaar', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            });
        },
    };
}]);
