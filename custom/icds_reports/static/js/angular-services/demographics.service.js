var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var demographicsServiceEventCategory = google.trackCategory('Demographics Service');

window.angular.module('icdsApp').factory('demographicsService', ['$http', function($http) {
    return {
        getRegisteredHouseholdData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Registered Household', {'step': step, 'params': params}
            );
            var get_url = url('registered_household', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Registered Household', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Registered Household', {'step': step, 'params': params}
                    );
                },
            );
        },
        getEnrolledChildrenData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Enrolled Children', {'step': step, 'params': params}
            );
            var get_url = url('enrolled_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Enrolled Children', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Enrolled Children', {'step': step, 'params': params}
                    );
                },
            );
        },
        getEnrolledWomenData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Enrolled Women', {'step': step, 'params': params}
            );
            var get_url = url('enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Enrolled Women', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Enrolled Women', {'step': step, 'params': params}
                    );
                },
            );
        },
        getLactatingEnrolledWomenData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Lactating Enrolled Women', {'step': step, 'params': params}
            );
            var get_url = url('lactating_enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Lactating Enrolled Women', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Lactating Enrolled Women', {'step': step, 'params': params}
                    );
                },
            );
        },
        getAdolescentGirlsData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Adolescent Girls', {'step': step, 'params': params}
            );
            var get_url = url('adolescent_girls', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Adolescent Girls', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Adolescent Girls', {'step': step, 'params': params}
                    );
                },
            );
        },
        getAdhaarData: function(step, params) {
            demographicsServiceEventCategory.event(
                'Fetching data started', 'Adhaar Beneficiaries', {'step': step, 'params': params}
            );
            var get_url = url('adhaar', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    demographicsServiceEventCategory.event(
                        'Fetching data succeeded', 'Adhaar Beneficiaries', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    demographicsServiceEventCategory.event(
                        'Fetching data failed', 'Adhaar Beneficiaries', {'step': step, 'params': params}
                    );
                },
            );
        },
    };
}]);
