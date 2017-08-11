var url = hqImport('hqwebapp/js/urllib.js').reverse;

window.angular.module('icdsApp').factory('locationsService', ['$http', function($http) {
    return {
        getRootLocations: function() {
            return this.getChildren(null);
        },
        getChildren: function(parentId) {
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId},
            }).then(function(response) {
                return response.data;
            });
        },
        getAncestors: function(locationId) {
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId},
            }).then(function(response) {
                return response.data;
            });
        },
        getLocation: function(locationId) {
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId},
            }).then(function(response) {
                return response.data;
            });
        },
        getLocationByNameAndParent: function(name, parentId) {
            return $http.get(url('icds_locations'), {
                params: {name: name, parent_id: parentId},
            }).then(function(response) {
                return response.data.locations;
            });
        },
    };
}]);
