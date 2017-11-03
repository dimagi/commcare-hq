window.angular.module('icdsApp').factory('storageService', ['userLocationId', function(userLocationId) {
    var storage = {
        'search': {
            'location_id': userLocationId,
        },
        'last_page': "",
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
        setKey: function(key, value) {
            storage[key] = value;
        },
    };
}]);