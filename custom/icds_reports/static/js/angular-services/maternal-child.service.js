window.angular.module('icdsApp').factory('maternalChildService', ['$http', '$q', function($http, $q) {
    return {
        getUnderweightChildrenData: function() {
            var get_url = url('underweight_children', '---');
            return  $http({
                method: "GET",
                url: get_url,
                params: {},
            });
        },
    };
}]);