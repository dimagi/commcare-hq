var url = hqImport('hqwebapp/js/initial_page_data').reverse;

window.angular.module('icdsApp').factory('maternalChildService', ['$http', function($http) {
    return {
        getUnderweightChildrenData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Underweight Children',
            });
            var get_url = url('underweight_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Underweight Children',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Underweight Children',
                    });
                }
            );
        },
        getPrevalenceOfSevereData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Prevalence Of Severe',
            });
            var get_url = url('prevalence_of_severe', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Prevalence Of Severe',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Prevalence Of Severe',
                    });
                }
            );
        },
        getPrevalenceOfStuntingData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Prevalence Of Stunting',
            });
            var get_url = url('prevalence_of_stunting', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Prevalence Of Stunting',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Prevalence Of Stunting',
                    });
                }
            );
        },
        getNewbornLowBirthData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Newborn Low Birth',
            });
            var get_url = url('low_birth', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Newborn Low Birth',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Newborn Low Birth',
                    });
                }
            );
        },
        earlyInitiationBreastfeeding: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Early Initiation Breastfeeding',
            });
            var get_url = url('early_initiation', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Early Initiation Breastfeeding',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Early Initiation Breastfeeding',
                    });
                }
            );
        },
        getExclusiveBreastfeedingData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Exclusive Breastfeeding',
            });
            var get_url = url('exclusive-breastfeeding', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Exclusive Breastfeeding',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Exclusive Breastfeeding',
                    });
                }
            );
        },
        getChildrenInitiatedData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Children Initiated',
            });
            var get_url = url('children_initiated', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Children Initiated',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Children Initiated',
                    });
                }
            );
        },
        getInstitutionalDeliveriesData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Institutional Deliveries',
            });
            var get_url = url('institutional_deliveries', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Institutional Deliveries',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Institutional Deliveries',
                    });
                }
            );
        },
        getImmunizationCoverageData: function(step, params) {
            window.ga('send', 'event', {
                'eventCategory': 'Maternal Child Service',
                'eventAction': 'Fetching data started',
                'eventLabel': 'Immunization Coverage',
            });
            var get_url = url('immunization_coverage', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data succeeded',
                        'eventLabel': 'Immunization Coverage',
                    });
                    return response;
                },
                function() {
                    window.ga('send', 'event', {
                        'eventCategory': 'Maternal Child Service',
                        'eventAction': 'Fetching data failed',
                        'eventLabel': 'Immunization Coverage',
                    });
                }
            );
        },
    };
}]);
