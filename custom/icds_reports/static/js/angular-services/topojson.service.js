window.angular.module('icdsApp').factory('topojsonService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var CACHE = {
        blocks: {}
    };

    return {
        getTopoJsonForDistrict: function (district) {
            if (district in CACHE["blocks"]) {
                // https://javascript.info/promise-api#promise-resolve-reject
                return Promise.resolve(CACHE["blocks"][district]);
            } else {
                return $http.get(url('topojson'), {
                    params: {district: district},
                }).then(
                    function (response) {
                        CACHE['blocks'][district] = response.data;
                        return response.data;
                    },
                    function () {
                        console.error(error);
                    }
                );
            }
        },
    };
}]);
