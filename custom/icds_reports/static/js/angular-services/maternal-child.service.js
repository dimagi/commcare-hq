window.angular.module('icdsApp').factory('maternalChildService', ['$http', '$q', function($http, $q) {
    return {
        getUnderweightChildrenData: function() {
            // mock data
            return $q(function(resolve) {
                setTimeout(function() {
                    resolve({
                        data: {
                            "IN.": {
                                "fillKey": "26%-50%",
                            },
                            "IN.MH": {
                                "fillKey": "76%-100%",
                            },
                            "IN.UP": {
                                "fillKey": "51%-75%",
                            },
                            "IN.OR": {
                                "fillKey": "26%-50%",
                            },
                        },
                    });
                }, 1000);
            });
        },
    };
}]);