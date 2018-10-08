var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var gtag = hqImport('analytix/js/google').track;

window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', function($http, $location) {
    return {
        getRootLocations: function() {
            return this.getChildren(null);
        },
        getChildren: function(parentId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getChildren');
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getChildren');
                    return response.data;
                },
                function() {
                    gtag.event('Location Service', 'Fetching data failed', 'getChildren');
                }
            );
        },
        getAncestors: function(locationId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getAncestors');
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getAncestors');
                    return response.data;
                },
                function() {
                    gtag.event('Location Service', 'Fetching data failed', 'getAncestors');
                }
            );
        },
        getLocation: function(locationId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getLocation');
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getLocation');
                    return response.data;
                },
                function() {
                    gtag.event('Location Service', 'Fetching data failed', 'getLocation');
                }
            );
        },
        getLocationByNameAndParent: function(name, parentId) {
            var includeTest = $location.search()['include_test'];
            gtag.event('Location Service', 'Fetching data started', 'getLocationByNameAndParent');
            return $http.get(url('icds_locations'), {
                params: {name: name, parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getLocationByNameAndParent');
                    return response.data.locations;
                },
                function() {
                    gtag.event('Location Service', 'Fetching data failed', 'getLocationByNameAndParent');
                }
            );
        },
        getAwcLocations: function(locationId) {
            gtag.event('Location Service', 'Fetching data started', 'getAwcLocations');
            return $http.get(url('awc_locations'), {
                params: {location_id: locationId},
            }).then(
                function(response) {
                    gtag.event('Location Service', 'Fetching data succeeded', 'getAwcLocations');
                    return response.data.locations;
                },
                function() {
                    gtag.event('Location Service', 'Fetching data failed', 'getAwcLocations');
                }
            );
        },
    };
}]);
