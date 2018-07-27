var url = hqImport('hqwebapp/js/initial_page_data').reverse;
var google = hqImport('analytix/js/google');
var maternalChildServiceEventCategory = google.trackCategory('Maternal Child Service');

window.angular.module('icdsApp').factory('maternalChildService', ['$http', function($http) {
    return {
        getUnderweightChildrenData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Underweight Children', [step, params]
            );
            var get_url = url('underweight_children', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Underweight Children', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Underweight Children', {'step': step, 'params': params}
                    );
                },
            );
        },
        getPrevalenceOfSevereData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Prevalence Of Severe', [step, params]
            );
            var get_url = url('prevalence_of_severe', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Prevalence Of Severe', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Prevalence Of Severe', {'step': step, 'params': params}
                    );
                },
            );
        },
        getPrevalenceOfStuntingData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Prevalence Of Stunting', [step, params]
            );
            var get_url = url('prevalence_of_stunting', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Prevalence Of Stunting', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Prevalence Of Stunting', {'step': step, 'params': params}
                    );
                },
            );
        },
        getNewbornLowBirthData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Newborn Low Birth', [step, params]
            );
            var get_url = url('low_birth', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Newborn Low Birth', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Newborn Low Birth', {'step': step, 'params': params}
                    );
                },
            );
        },
        earlyInitiationBreastfeeding: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Early Initiation Breastfeeding', [step, params]
            );
            var get_url = url('early_initiation', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Early Initiation Breastfeeding',
                        {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Early Initiation Breastfeeding', {'step': step, 'params': params}
                    );
                },
            );
        },
        getExclusiveBreastfeedingData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Exclusive Breastfeeding', [step, params]
            );
            var get_url = url('exclusive-breastfeeding', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Exclusive Breastfeeding', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Exclusive Breastfeeding', {'step': step, 'params': params}
                    );
                },
            );
        },
        getChildrenInitiatedData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Children Initiated', [step, params]
            );
            var get_url = url('children_initiated', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Children Initiated', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Children Initiated', {'step': step, 'params': params}
                    );
                },
            );
        },
        getInstitutionalDeliveriesData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Institutional Deliveries', [step, params]
            );
            var get_url = url('institutional_deliveries', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Institutional Deliveries', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Institutional Deliveries', {'step': step, 'params': params}
                    );
                },
            );
        },
        getImmunizationCoverageData: function(step, params) {
            maternalChildServiceEventCategory.event(
                'Fetching data started', 'Immunization Coverage', [step, params]
            );
            var get_url = url('immunization_coverage', step);
            return  $http({
                method: "GET",
                url: get_url,
                params: params,
            }).then(
                function(response) {
                    maternalChildServiceEventCategory.event(
                        'Fetching data succeeded', 'Immunization Coverage', {'step': step, 'params': params}
                    );
                    return response;
                },
                function() {
                    maternalChildServiceEventCategory.event(
                        'Fetching data failed', 'Immunization Coverage', {'step': step, 'params': params}
                    );
                },
            );
        },
    };
}]);
