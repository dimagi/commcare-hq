var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('champApp').factory('reportsDataService', ['$http', function($http) {
    return {
        getPrevisionVsAchievementsData: function(filters) {
            var get_url = url('champ_pva');
            return  $http({
                method: "GET",
                url: get_url,
                params: filters,
            });
        },
    };
}]);
