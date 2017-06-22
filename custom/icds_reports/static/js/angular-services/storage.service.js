window.angular.module('icdsApp').factory('storageService', ['userLocationId', function(userLocationId) {
    var storage = {
        'location': userLocationId,
    };

    return {
        get: function () {
            return storage;
        },
        set: function (data) {
            storage = data;
        },
        getKey: function(key) {
            return storage[key];
        },
    };
}]);