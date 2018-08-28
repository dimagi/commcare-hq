var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('demographicsService', ['$http', function($http) {
    return {
        getRegisteredHouseholdData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Registered Household',
            });
            var get_url = url('registered_household', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Registered Household',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Registered Household',
                    });
                }
            );
        },
        getEnrolledChildrenData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Enrolled Children',
            });
            var get_url = url('enrolled_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Enrolled Children',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Enrolled Children',
                    });
                }
            );
        },
        getEnrolledWomenData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Enrolled Women',
            });
            var get_url = url('enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Enrolled Women',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Enrolled Women',
                    });
                }
            );
        },
        getLactatingEnrolledWomenData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Lactating Enrolled Women',
            });
            var get_url = url('lactating_enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Lactating Enrolled Women',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Lactating Enrolled Women',
                    });
                }
            );
        },
        getAdolescentGirlsData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Adolescent Girls',
            });
            var get_url = url('adolescent_girls', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Adolescent Girls',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Adolescent Girls',
                    });
                }
            );
        },
        getAdhaarData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Demographics Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Adhaar Beneficiaries',
            });
            var get_url = url('adhaar', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Adhaar Beneficiaries',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Demographics Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Adhaar Beneficiaries',
                    });
                }
            );
        },
    };
}]);
