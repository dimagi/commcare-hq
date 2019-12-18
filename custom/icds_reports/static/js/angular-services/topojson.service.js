window.angular.module('icdsApp').factory('topojsonService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    // todo: is there a better way to generate this so it works with django?
    var stateTopoJsonUrl = '/static/js/topojsons/states_v3_small.topojson';
    var CACHE = {
        blocks: {}
    };

    return {
        getStateTopoJson: function () {
            console.log("get state topojson");
            if ("states" in CACHE) {
                console.log("cache hit");

                // https://javascript.info/promise-api#promise-resolve-reject
                return Promise.resolve(CACHE["states"]);
            } else {
                console.log("cache misss");
                return $http.get(stateTopoJsonUrl).then(
                    function (response) {
                        console.log('http get response');
                        CACHE['states'] = response.data;
                        console.log('state response', response.data);
                        return response.data;
                    },
                );
            }
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
