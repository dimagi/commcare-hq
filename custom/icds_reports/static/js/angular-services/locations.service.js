var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', function($http, $location) {
    var includeTest = $location.search()['include_test'];
    return {
        getRootLocations: function() {
            return this.getChildren(null);
        },
        getChildren: function(parentId) {
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId, include_test: includeTest},
            }).then(function(response) {
                return response.data;
            });
        },
        getAncestors: function(locationId) {
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(function(response) {
                return response.data;
            });
        },
        getLocation: function(locationId) {
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(function(response) {
                return response.data;
            });
        },
        getLocationByNameAndParent: function(name, parentId) {
            return $http.get(url('icds_locations'), {
                params: {name: name, parent_id: parentId, include_test: includeTest},
            }).then(function(response) {
                return response.data.locations;
            });
        },
        getAwcLocations: function(locationId) {
            return $http.get(url('awc_locations'), {
                params: {location_id: locationId},
            }).then(function(response) {
                return response.data.locations;
            });
        },
    };
}]);
