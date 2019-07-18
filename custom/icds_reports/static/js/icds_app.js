/* global d3, moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MainController($scope, $route, $routeParams, $location, $uibModal, $window, $http, reportAnIssueUrl, isWebUser, userLocationId) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.isWebUser = isWebUser;

    var locationParams = $location.search();
    var newKey;
    for (var key in locationParams) {
        newKey = key;
        if (newKey.startsWith('amp;')) {
            newKey = newKey.slice(4);
            $location.search(newKey, locationParams[key]).search(key, null);
        }
    }

    $scope.reportAnIssue = function() {
        if (reportAnIssueUrl) {
            $window.location.href = reportAnIssueUrl;
            return;
        }
        $uibModal.open({
            ariaLabelledBy: 'modal-title',
            ariaDescribedBy: 'modal-body',
            templateUrl: 'reportIssueModal.html',
        });
    };

    $scope.updateCssClasses = function () {
        if (window.angular.element('.alert-maintenance').children().length === 1) {
            var elementsToUpdate = ['left-menu', 'fixed-title', 'fixes-filters', 'main-container'];

            _.each(elementsToUpdate, function (element) {
                window.angular.element('.' + element).addClass(element + '-with-alert');
            });
        }
    };

    $scope.checkAccessToLocation = function() {
        var locationId = $location.search()['location_id'];
        if (userLocationId !== void(0) && ['', 'undefinded', 'null', void(0)].indexOf(locationId) === -1) {
            $http.get(url('have_access_to_location'), {
                params: {location_id: locationId},
            }).then(function (response) {
                if ($scope.$location.$$path !== '/access_denied' && !response.data.haveAccess) {
                    $scope.$evalAsync(function () {
                        $location.search('location_id', userLocationId);
                        $location.path('/access_denied');
                        $window.location.href = '#/access_denied';
                    });
                }
            });
        }
    };

    $scope.$on('$routeChangeStart', function() {
        $scope.checkAccessToLocation();
        var path = window.location.pathname + $location.path().substr(1);
        $window.ga('set', 'page', path);
        $window.ga('send', 'pageview', path);
    });

    // hack to have the same width between origin table and fixture headers,
    // without this fixture headers are bigger and not align to original columns
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes && mutation.addedNodes.length > 0) {
                var hasClass = [].some.call(mutation.addedNodes, function(el) {
                    return el.classList !== void(0) && el.classList.contains('fixedHeader-floating');
                });
                if (hasClass) {
                    if ($scope.$route.current.pathParams.step === 'beneficiary') {
                        var fixedTitle = d3.select('.fixed-title')[0][0].clientHeight;
                        var fixedFilters = d3.select('.fixes-filters')[0][0].clientHeight;
                        var width = "width: " + mutation.addedNodes[0].style.width + ' !important;'
                            + 'top:' + (fixedTitle + fixedFilters - 8) + 'px !important;';
                        mutation.addedNodes[0].style.cssText = (mutation.addedNodes[0].style.cssText + width);
                    } else {
                        mutation.addedNodes[0].style.cssText = (mutation.addedNodes[0].style.cssText + 'display: none;');
                    }
                }
            }
        });
    });

    var config = {
        attributes: true,
        childList: true,
        characterData: true,
    };

    observer.observe(document.body, config);
}

MainController.$inject = [
    '$scope',
    '$route',
    '$routeParams',
    '$location',
    '$uibModal',
    '$window',
    '$http',
    'reportAnIssueUrl',
    'isWebUser',
    'userLocationId',
];

window.angular.module('icdsApp', ['ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap', 'nvd3', 'datatables', 'datatables.bootstrap', 'datatables.fixedcolumns', 'datatables.fixedheader', 'leaflet-directive', 'cgBusy', 'perfect_scrollbar'])
    .controller('MainController', MainController)
    .config(['$interpolateProvider', '$routeProvider', function($interpolateProvider, $routeProvider) {
        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');

        $routeProvider
            .when("/", {
                redirectTo: '/program_summary/maternal_child',
            }).when("/program_summary/:step", {
                template: "<system-usage></system-usage>",
            }).when("/awc_opened", {
                redirectTo: "/awc_opened/map",
            })
            .when("/awc_opened/:step", {
                template: "<awc-opened-yesterday></awc-opened-yesterday>",
            })
            .when("/active_awws", {
                template: "active_awws",
            })
            .when("/submitted_yesterday", {
                template: "submitted_yesterday",
            })
            .when("/submitted", {
                template: "submitted",
            })
            .when("/system_usage_tabular", {
                template: "system_usage_tabular",
            })
            .when("/comp_feeding", {
                template: "comp_feeding",
            })
            .when("/health_tabular_report", {
                template: "health_tabular_report",
            })
            .when("/maternal_and_child", {
                redirectTo: "/maternal_and_child/underweight_children/map",
            })
            .when("/maternal_and_child/underweight_children", {
                redirectTo: "/maternal_and_child/underweight_children/map",
            })
            .when("/maternal_and_child/underweight_children/:step", {
                template: "<underweight-children-report></underweight-children-report>",
            })
            .when("/maternal_and_child/wasting", {
                redirectTo: "/maternal_and_child/wasting/map",
            })
            .when("/maternal_and_child/wasting/:step", {
                template: "<prevalence-of-severe></prevalence-of-severe>",
            })
            .when("/maternal_and_child/stunting", {
                redirectTo: "/maternal_and_child/stunting/map",
            })
            .when("/maternal_and_child/stunting/:step", {
                template: "<prevalence-of-stunting></prevalence-of-stunting>",
            })
            .when("/maternal_and_child/low_birth", {
                redirectTo: "/maternal_and_child/low_birth/map",
            })
            .when("/maternal_and_child/low_birth/:step", {
                template: "<newborn-low-weight></newborn-low-weight>",
            })
            .when("/maternal_and_child/early_initiation", {
                redirectTo: "/maternal_and_child/early_initiation/map",
            })
            .when("/maternal_and_child/early_initiation/:step", {
                template: "<early-initiation-breastfeeding></early-initiation-breastfeeding>",
            })
            .when("/maternal_and_child/exclusive_breastfeeding", {
                redirectTo: "/maternal_and_child/exclusive_breastfeeding/map",
            })
            .when("/maternal_and_child/exclusive_breastfeeding/:step", {
                template: "<exclusive-breastfeeding></exclusive-breastfeeding>",
            })
            .when("/maternal_and_child/children_initiated", {
                redirectTo: "/maternal_and_child/children_initiated/map",
            })
            .when("/maternal_and_child/children_initiated/:step", {
                template: "<children-initiated></children-initiated>",
            })
            .when("/maternal_and_child/institutional_deliveries", {
                redirectTo: "/maternal_and_child/institutional_deliveries/map",
            })
            .when("/maternal_and_child/institutional_deliveries/:step", {
                template: "<institutional-deliveries></institutional-deliveries>",
            })
            .when("/maternal_and_child/immunization_coverage", {
                redirectTo: "/maternal_and_child/immunization_coverage/map",
            })
            .when("/maternal_and_child/immunization_coverage/:step", {
                template: "<immunization-coverage></immunization-coverage>",
            })
            .when("/icds_cas_reach", {
                redirectTo: "/icds_cas_reach/awc_daily_status/map",
            })
            .when("/icds_cas_reach/awc_daily_status", {
                redirectTo: "/icds_cas_reach/awc_daily_status/map",
            })
            .when("/icds_cas_reach/awc_daily_status/:step", {
                template: "<awc-daily-status></awc-daily-status>",
            })
            .when("/icds_cas_reach/awcs_covered", {
                redirectTo: "/icds_cas_reach/awcs_covered/map",
            })
            .when("/icds_cas_reach/awcs_covered/:step", {
                template: "<awcs-covered></awcs-covered>",
            })
            .when("/demographics", {
                redirectTo: "/demographics/registered_household/map",
            })
            .when("/demographics/registered_household", {
                redirectTo: "/demographics/registered_household/map",
            })
            .when("/demographics/registered_household/:step", {
                template: "<registered-household></registered-household>",
            })
            .when("/demographics/enrolled_children", {
                redirectTo: "/demographics/enrolled_children/map",
            })
            .when("/demographics/enrolled_children/:step", {
                template: "<enrolled-children></enrolled-children>",
            })
            .when("/demographics/enrolled_women", {
                redirectTo: "/demographics/enrolled_women/map",
            })
            .when("/demographics/enrolled_women/:step", {
                template: "<enrolled-women></enrolled-women>",
            })
            .when("/demographics/lactating_enrolled_women", {
                redirectTo: "/demographics/lactating_enrolled_women/map",
            })
            .when("/demographics/lactating_enrolled_women/:step", {
                template: "<lactating-enrolled-women></lactating-enrolled-women>",
            })
            .when("/demographics/adolescent_girls", {
                redirectTo: "/demographics/adolescent_girls/map",
            })
            .when("/demographics/adolescent_girls/:step", {
                template: "<adolescent-girls></adolescent-girls>",
            })
            .when("/demographics/adhaar", {
                redirectTo: "/demographics/adhaar/map",
            })
            .when("/demographics/adhaar/:step", {
                template: "<adhaar-beneficiary></adhaar-beneficiary>",
            })
            .when("/awc_infrastructure", {
                redirectTo: "/awc_infrastructure/clean_water/map",
            })
            .when("/awc_infrastructure/clean_water", {
                redirectTo: "/awc_infrastructure/clean_water/map",
            })
            .when("/awc_infrastructure/clean_water/:step", {
                template: "<clean-water></clean-water>",
            })
            .when("/awc_infrastructure/functional_toilet", {
                redirectTo: "/awc_infrastructure/functional_toilet/map",
            })
            .when("/awc_infrastructure/functional_toilet/:step", {
                template: "<functional-toilet></functional-toilet>",
            })
            .when("/awc_infrastructure/medicine_kit", {
                redirectTo: "/awc_infrastructure/medicine_kit/map",
            })
            .when("/awc_infrastructure/medicine_kit/:step", {
                template: "<medicine-kit></medicine-kit>",
            })
            .when("/awc_infrastructure/infants_weight_scale", {
                redirectTo: "/awc_infrastructure/infants_weight_scale/map",
            })
            .when("/awc_infrastructure/infants_weight_scale/:step", {
                template: "<infants-weight-scale></infants-weight-scale>",
            })
            .when("/awc_infrastructure/adult_weight_scale", {
                redirectTo: "/awc_infrastructure/adult_weight_scale/map",
            })
            .when("/awc_infrastructure/adult_weight_scale/:step", {
                template: "<adult-weight-scale></adult-weight-scale>",
            })
            .when("/awc_reports", {
                redirectTo: "/awc_reports/pse",
            })
            .when("/service_delivery_dashboard", {
                redirectTo: "/service_delivery_dashboard/pw_lw_children",
            })
            .when("/service_delivery_dashboard/:step", {
                template: "<service-delivery-dashboard></service-delivery-dashboard>",
            })
            .when("/awc_reports/:step", {
                template: "<awc-reports></awc-reports>",
            })
            .when("/lady_supervisor", {
                template: "<lady-supervisor></lady-supervisor>",
            })
            .when("/download", {
                template: "<download></download>",
            })
            .when("/fact_sheets", {
                template: "<progress-report></progress-report>",
            })
            .when("/fact_sheets/:report", {
                template: "<progress-report></progress-report>",
            })
            .when("/cas_export", {
                template: "<cas-export></cas-export>",
            })
            .when("/access_denied", {
                template: "<access-denied></access-denied>",
            });
    }]);

