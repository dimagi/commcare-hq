window.angular.module('icdsApp').factory('maternalChildService', ['$http', function ($http) {
    var url = hqImport('hqwebapp/js/initial_page_data').reverse;
    var gtag = hqImport('analytix/js/google').track;
    return {
        getUnderweightChildrenData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Underweight Children');
            var get_url = url('underweight_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Underweight Children');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Underweight Children');
                }
            );
        },
        getPrevalenceOfSevereData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Prevalence Of Severe');
            var get_url = url('prevalence_of_severe', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Prevalence Of Severe');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Prevalence Of Severe');
                }
            );
        },
        getPrevalenceOfStuntingData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Prevalence Of Stunting');
            var get_url = url('prevalence_of_stunting', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Prevalence Of Stunting');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Prevalence Of Stunting');
                }
            );
        },
        getNewbornLowBirthData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Newborn Low Birth');
            var get_url = url('low_birth', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Newborn Low Birth');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Newborn Low Birth');
                }
            );
        },
        earlyInitiationBreastfeeding: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Early Initiation Breastfeeding');
            var get_url = url('early_initiation', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event(
                        'Maternal Child Service',
                        'Fetching data succeeded',
                        'Early Initiation Breastfeeding'
                    );
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Early Initiation Breastfeeding');
                }
            );
        },
        getExclusiveBreastfeedingData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Exclusive Breastfeeding');
            var get_url = url('exclusive-breastfeeding', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Exclusive Breastfeeding');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Exclusive Breastfeeding');
                }
            );
        },
        getChildrenInitiatedData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Children Initiated');
            var get_url = url('children_initiated', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Children Initiated');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Children Initiated');
                }
            );
        },
        getInstitutionalDeliveriesData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Institutional Deliveries');
            var get_url = url('institutional_deliveries', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Institutional Deliveries');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Institutional Deliveries');
                }
            );
        },
        getImmunizationCoverageData: function (step, params) {
            gtag.event('Maternal Child Service', 'Fetching data started', 'Immunization Coverage');
            var get_url = url('immunization_coverage', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function (response) {
                    gtag.event('Maternal Child Service', 'Fetching data succeeded', 'Immunization Coverage');
                    return response;
                },
                function () {
                    gtag.event('Maternal Child Service', 'Fetching data failed', 'Immunization Coverage');
                }
            );
        },
    };
}]);
