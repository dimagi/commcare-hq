var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', function($http, $location) {
    return {
        getRootLocations: function() {
            return this.getChildren(null);
        },
        getChildren: function(parentId) {
            var includeTest = $location.search()['include_test'];
            window.ga('send', 'event', {
                'eventCategory': 'Location Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getChildren',
            });
            return $http.get(url('icds_locations'), {
                params: {parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getChildren',
                    });
                    return response.data;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getChildren',
                    });
                }
            );
        },
        getAncestors: function(locationId) {
            var includeTest = $location.search()['include_test'];
            window.ga('send', 'event', {
                'eventCategory': 'Location Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getAncestors',
            });
            return $http.get(url('icds_locations_ancestors'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getAncestors',
                    });
                    return response.data;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getAncestors',
                    });
                }
            );
        },
        getLocation: function(locationId) {
            var includeTest = $location.search()['include_test'];
            window.ga('send', 'event', {
                'eventCategory': 'Location Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getLocation',
            });
            return $http.get(url('icds_locations'), {
                params: {location_id: locationId, include_test: includeTest},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getLocation',
                    });
                    return response.data;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getLocation',
                    });
                }
            );
        },
        getLocationByNameAndParent: function(name, parentId) {
            var includeTest = $location.search()['include_test'];
            window.ga('send', 'event', {
                'eventCategory': 'Location Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getLocationByNameAndParent',
            });
            return $http.get(url('icds_locations'), {
                params: {name: name, parent_id: parentId, include_test: includeTest},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getLocationByNameAndParent',
                    });
                    return response.data.locations;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getLocationByNameAndParent',
                    });
                }
            );
        },
        getAwcLocations: function(locationId) {
            window.ga('send', 'event', {
                'eventCategory': 'Location Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'getAwcLocations',
            });
            return $http.get(url('awc_locations'), {
                params: {location_id: locationId},
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'getAwcLocations',
                    });
                    return response.data.locations;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Location Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'getAwcLocations',
                    });
                }
            );
        },
    };
}]);
