/* global Promise */

window.angular.module('icdsApp').factory('topojsonService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    // todo: is there a better way to generate this so it works with django?
    var stateTopoJsonUrl = '/static/js/topojsons/states_v4.topojson';
    var districtTopoJsonUrl = '/static/js/topojsons/districts_v4.topojson';
    var CACHE = {
        blocks: {},
    };
    function getStaticTopojson(topojsonUrl, cacheKey) {
        if (cacheKey in CACHE) {
            // https://javascript.info/promise-api#promise-resolve-reject
            return Promise.resolve(CACHE[cacheKey]);
        } else {
            return $http.get(topojsonUrl).then(
                function (response) {
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
        getBlockTopoJsonForState: function (state) {
            var cacheKey = state;
            if (cacheKey in CACHE["blocks"]) {
                // https://javascript.info/promise-api#promise-resolve-reject
                return Promise.resolve(CACHE["blocks"][cacheKey]);
            } else {
                return $http.get(url('topojson'), {
                    params: {state: state},
                }).then(
                    function (response) {
                        CACHE['blocks'][cacheKey] = response.data;
                        return response.data;
                    }
                );
            }
        },
    };
}]);
