window.angular.module('icdsApp').factory('locationsService', ['$http', '$location', 'storageService', 'navigationService', function($http, $location, storageService, navigationService) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;

    function transformLocationTypeName(locationTypeName) {
        if (locationTypeName === 'awc') {
            return locationTypeName.toUpperCase();
        } else if (locationTypeName === 'supervisor') {
            return 'Sector';
        } else {
            return locationTypeName.charAt(0).toUpperCase() + locationTypeName.slice(1);
        }
    }

    function getLocationByNameAndParent(name, parentId) {
        var includeTest = $location.search()['include_test'];
        gtag.event('Location Service', 'Fetching data started', 'getLocationByNameAndParent');
        return $http.get(url('icds_locations'), {
            params: {name: name, parent_id: parentId, include_test: includeTest},
        }).then(
            function (response) {
                gtag.event('Location Service', 'Fetching data succeeded', 'getLocationByNameAndParent');
                return response.data.locations;
            },
            function () {
                gtag.event('Location Service', 'Fetching data failed', 'getLocationByNameAndParent');
            }
        );
    }
    function tryToNavigateToLocation(locationName, parentLocationId) {
        getLocationByNameAndParent(locationName, parentLocationId).then(function (locations) {
            var location = locations[0];
            if (location) {
                $location.search('location_name', location.name);
                $location.search('location_id', location.location_id);
                storageService.setKey('search', $location.search());
                if (location.location_type_name === 'awc') {
                    $location.path(navigationService.getAWCTabFromPagePath($location.path()));
                }
            }
        });
    }

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
        getLocationByNameAndParent: getLocationByNameAndParent,
        tryToNavigateToLocation: tryToNavigateToLocation,
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
        transformLocationTypeName: transformLocationTypeName,
        locationTypesToDisplay: function (locationTypes) {
            return _.map(locationTypes, function (locationType) {
                return transformLocationTypeName(locationType.name);
            }).join(', ');
        },
        locationTypeIsVisible: function (selectedLocations, level) {
            // whether a location type is visible (should be selectable) from locations service
            // hard code reports that disallow drilling past a certain level
            if (($location.path().indexOf('lady_supervisor') !== -1 || $location.path().indexOf('service_delivery_dashboard') !== -1) && level === 4) {
                return false;
            }
            // otherwise
            return (
                level === 0 ||  // first level to select should be visible
                // or previous location should be set and not equal to "all".
                (selectedLocations[level - 1] && selectedLocations[level - 1] !== 'all' && selectedLocations[level - 1].location_id !== 'all')
            );
        },
        getLocationsForLevel: function (level, selectedLocations, locationsCache) {
            if (level === 0) {
                return locationsCache.root;
            } else {
                var selectedLocation = selectedLocations[level - 1];
                if (!selectedLocation || selectedLocation.location_id === 'all') {
                    return [];
                }
                return locationsCache[selectedLocation.location_id];
            }
        },
    };
}]);
