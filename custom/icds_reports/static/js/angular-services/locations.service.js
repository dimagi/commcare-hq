var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var locationServiceEventCategory = google.trackCategory('Location Service');

window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', function($http, $location) {
    return {
        getRootLocations: function() {
            return this.getChildren(null);
        },
        getChildren: function(parentId) {
            var includeTest = $location.search()['include_test'];
            locationServiceEventCategory.event(
                'Fetching data started', 'getChildren', {'parentId': parentId}
            );
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    locationServiceEventCategory.event(
                        'Fetching data succeeded', 'getChildren', {'parentId': parentId}
                    );
                    return response.data;
                },
                function() {
                    locationServiceEventCategory.event(
                        'Fetching data failed', 'getChildren', {'parentId': parentId}
                    );
                }
            );
        },
        getAncestors: function(locationId) {
            var includeTest = $location.search()['include_test'];
            locationServiceEventCategory.event(
                'Fetching data started', 'getAncestors', {'locationId': locationId}
            );
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    locationServiceEventCategory.event(
                        'Fetching data succeeded', 'getAncestors', {'locationId': locationId}
                    );
                    return response.data;
                },
                function() {
                    locationServiceEventCategory.event(
                        'Fetching data failed', 'getAncestors', {'locationId': locationId}
                    );
                }
            );
        },
        getLocation: function(locationId) {
            var includeTest = $location.search()['include_test'];
            locationServiceEventCategory.event(
                'Fetching data started', 'getLocation', {'locationId': locationId}
            );
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    locationServiceEventCategory.event(
                        'Fetching data succeeded', 'getLocation', {'locationId': locationId}
                    );
                    return response.data;
                },
                function() {
                    locationServiceEventCategory.event(
                        'Fetching data failed', 'getLocation', {'locationId': locationId}
                    );
                }
            );
        },
        getLocationByNameAndParent: function(name, parentId) {
            var includeTest = $location.search()['include_test'];
            locationServiceEventCategory.event(
                'Fetching data started', 'getLocationByNameAndParent', {'name': name, 'parentId': parentId}
            );
            return $http.get(url('icds_locations'), {
                params: {name: name, parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    locationServiceEventCategory.event(
                        'Fetching data succeeded', 'getLocationByNameAndParent',
                        {'name': name, 'parentId': parentId}
                    );
                    return response.data.locations;
                },
                function() {
                    locationServiceEventCategory.event(
                        'Fetching data failed', 'getLocationByNameAndParent', {'name': name, 'parentId': parentId}
                    );
                }
            );
        },
        getAwcLocations: function(locationId) {
            locationServiceEventCategory.event(
                'Fetching data started', 'getAwcLocations', {'locationId': locationId}
            );
            return $http.get(url('awc_locations'), {
                params: {location_id: locationId},
            }).then(
                function(response) {
                    locationServiceEventCategory.event(
                        'Fetching data succeeded', 'getAwcLocations', {'locationId': locationId}
                    );
                    return response.data.locations;
                },
                function() {
                    locationServiceEventCategory.event(
                        'Fetching data failed', 'getAwcLocations', {'locationId': locationId}
                    );
                }
            );
        },
    };
}]);
