window.angular.module('icdsApp').factory('maternalChildService', ['$http', '$q', function($http, $q) {
    return {
        getUnderweightChildrenData: function() {
            // mock data
            return $q(function(resolve) {
                setTimeout(function() {
                    resolve({
                        data: {
                            "Bihar": {
                                "fillKey": "26%-50%",
                            },
                            "Odisha": {
                                "fillKey": "76%-100%",
                            },
                            "Karnataka": {
                                "fillKey": "51%-75%",
                            },
                            "Mizoram": {
                                "fillKey": "26%-50%",
                            },
                        },
                    });
                }, 1000);
            });
        },
    };
}]);