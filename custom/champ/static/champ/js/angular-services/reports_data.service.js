var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('champApp').factory('reportsDataService', ['$http', function($http) {
    return {
        getPrevisionVsAchievementsData: function(filters) {
            var get_url = url('champ_pva');
            return  $http({
                method: "POST",
                url: get_url,
                params: filters,
            });
        },
        getPrevisionVsAchievementsTableData: function(filters) {
            var get_url = url('champ_pva_table');
            return  $http({
                method: "POST",
                url: get_url,
                params: filters,
            });
        },
        getServiceUptakeData: function(filters) {
            var get_url = url('service_uptake');
            return  $http({
                method: "POST",
                url: get_url,
                params: filters,
            });
        },
    };
}]);
