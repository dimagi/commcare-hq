window.angular.module('icdsApp').factory('topojsonService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    // todo: is there a better way to generate this so it works with django?
    var stateTopoJsonUrl = '/static/js/topojsons/states_v3_small.topojson';
    var districtTopoJsonUrl = '/static/js/topojsons/districts_v3_small.topojson';
    var CACHE = {
        blocks: {}
    };
    function getStaticTopojson(topojsonUrl, cacheKey) {
        if (cacheKey in CACHE) {
            console.log("cache hit");
            // https://javascript.info/promise-api#promise-resolve-reject
            return Promise.resolve(CACHE["states"]);
        } else {
            console.log("cache misss");
            return $http.get(topojsonUrl).then(
                function (response) {
                    console.log('http get response');
                    CACHE[cacheKey] = response.data;
                    return response.data;
                }
            );
        }
    }

    return {
        getStateTopoJson: function () {
            return getStaticTopojson(stateTopoJsonUrl, 'states');
        },
        getDistrictTopoJson: function () {
            return getStaticTopojson(districtTopoJsonUrl, 'districts');
        },
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
