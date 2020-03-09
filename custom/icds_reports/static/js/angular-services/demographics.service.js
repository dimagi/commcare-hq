window.angular.module('icdsApp').factory('demographicsService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    return {
        getRegisteredHouseholdData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Registered Household');
            var get_url = url('registered_household', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Registered Household');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Registered Household');
                }
            );
        },
        getEnrolledChildrenData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Enrolled Children');
            var get_url = url('enrolled_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Enrolled Children');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Enrolled Children');
                }
            );
        },
        getEnrolledWomenData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Enrolled Women');
            var get_url = url('enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Enrolled Women');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Enrolled Women');
                }
            );
        },
        getLactatingEnrolledWomenData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Lactating Enrolled Women');
            var get_url = url('lactating_enrolled_women', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Lactating Enrolled Women');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Lactating Enrolled Women');
                }
            );
        },
        getAdolescentGirlsData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Adolescent Girls');
            var get_url = url('adolescent_girls', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Adolescent Girls');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Adolescent Girls');
                }
            );
        },
        getAdhaarData: function (step, params) {
            gtag.event('Demographics Service', 'Fetching data started', 'Adhaar Beneficiaries');
            var get_url = url('adhaar', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Demographics Service', 'Fetching data succeeded', 'Adhaar Beneficiaries');
                    return response;
                },
                function () {
                    gtag.event('Demographics Service', 'Fetching data failed', 'Adhaar Beneficiaries');
                }
            );
        },
    };
}]);
