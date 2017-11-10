var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('champApp').factory('filtersService', ['$http', function($http) {
    return {
        districtFilter: function() {
            var get_url = url('district_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
        targetCBOFilter: function() {
            var get_url = url('target_cbo_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
        targetUserplFilter: function() {
            var get_url = url('target_userpl_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
        groupsFilter: function() {
            var get_url = url('group_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
        organizatioFilter: function() {
            var get_url = url('organization_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
        clienttypeFilter: function() {
            var get_url = url('clienttype_filter');
            return  $http({
                method: "GET",
                url: get_url,
            });
        },
    };
}]);
