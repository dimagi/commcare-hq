window.angular.module('icdsApp').factory('topojsonService', ['$http', function($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    return {
        getTopoJsonForDistrict: function(district) {
            return $http.get(url('topojson'), {
                params: {district: district},
            }).then(
                function(response) {
                    return response.data;
                },
                function() {
                    $log.error(error);
                }
            );
        },
    };
}]);
