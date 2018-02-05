/* global d3, moment */

function MainController($scope, $route, $routeParams, $location, $uibModal, $window, reportAnIssueUrl, isWebUser) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.isWebUser = isWebUser;
    var selected_month = parseInt($location.search()['month']) || new Date().getMonth() + 1;
    var selected_year = parseInt($location.search()['year']) || new Date().getFullYear();
    var current_month = new Date().getMonth() + 1;
    var current_year = new Date().getFullYear();

    if (selected_month === current_month && selected_year === current_year &&
        (new Date().getDate() === 1 || new Date().getDate() === 2)) {
        $scope.showInfoMessage = true;
        $scope.lastDayOfPreviousMonth = moment().set('date', 1).subtract(1, 'days').format('Do MMMM, YYYY');
        $scope.currentMonth = moment().format("MMMM");
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
    'reportAnIssueUrl',
    'isWebUser',
];

window.angular.module('icdsApp', ['ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap', 'nvd3', 'datatables', 'datatables.bootstrap', 'datatables.fixedcolumns', 'datatables.fixedheader', 'leaflet-directive', 'cgBusy', 'perfect_scrollbar'])
    .controller('MainController', MainController)
    .config(['$interpolateProvider', '$routeProvider', function($interpolateProvider, $routeProvider) {
        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');

        $routeProvider
            .when("/", {
                redirectTo : '/program_summary/maternal_child',
            }).when("/program_summary/:step", {
                template : "<system-usage></system-usage>",
            }).when("/awc_opened", {
                redirectTo : "/awc_opened/map",
            })
            .when("/awc_opened/:step", {
                template : "<awc-opened-yesterday></awc-opened-yesterday>",
            })
            .when("/active_awws", {
                template : "active_awws",
            })
            .when("/submitted_yesterday", {
                template : "submitted_yesterday",
            })
            .when("/submitted", {
                template : "submitted",
            })
            .when("/system_usage_tabular", {
                template : "system_usage_tabular",
            })
            .when("/underweight_children", {
                redirectTo : "/underweight_children/map",
            })
            .when("/underweight_children/:step", {
                template : "<underweight-children-report></underweight-children-report>",
            })
            .when("/wasting", {
                redirectTo : "/wasting/map",
            })
            .when("/wasting/:step", {
                template : "<prevalence-of-severe></prevalence-of-severe>",
            })
            .when("/stunting", {
                redirectTo : "/stunting/map",
            })
            .when("/stunting/:step", {
                template : "<prevalence-of-stunting></prevalence-of-stunting>",
            })
            .when("/comp_feeding", {
                template : "comp_feeding",
            })
            .when("/health_tabular_report", {
                template : "health_tabular_report",
            })
            .when("/awc_reports", {
                redirectTo : "/awc_reports/pse",
            })
            .when("/awc_reports/:step", {
                template : "<awc-reports></awc-reports>",
            })
            .when("/download", {
                template : "<download></download>",
            })
            .when("/fact_sheets", {
                template : "<progress-report></progress-report>",
            })
            .when("/fact_sheets/:report", {
                template : "<progress-report></progress-report>",
            })
            .when("/exclusive_breastfeeding", {
                redirectTo : "/exclusive_breastfeeding/map",
            })
            .when("/exclusive_breastfeeding/:step", {
                template: "<exclusive-breastfeeding></exclusive-breastfeeding>",
            })
            .when("/low_birth", {
                redirectTo : "/low_birth/map",
            })
            .when("/low_birth/:step", {
                template : "<newborn-low-weight></newborn-low-weight>",
            })
            .when("/early_initiation", {
                redirectTo : "/early_initiation/map",
            })
            .when("/early_initiation/:step", {
                template : "<early-initiation-breastfeeding></early-initiation-breastfeeding>",
            })
            .when("/children_initiated", {
                redirectTo : "/children_initiated/map",
            })
            .when("/children_initiated/:step", {
                template : "<children-initiated></children-initiated>",
            })
            .when("/institutional_deliveries", {
                redirectTo : "/institutional_deliveries/map",
            })
            .when("/institutional_deliveries/:step", {
                template : "<institutional-deliveries></institutional-deliveries>",
            })
            .when("/immunization_coverage", {
                redirectTo : "/immunization_coverage/map",
            })
            .when("/immunization_coverage/:step", {
                template : "<immunization-coverage></immunization-coverage>",
            })
            .when("/awc_daily_status", {
                redirectTo : "/awc_daily_status/map",
            })
            .when("/awc_daily_status/:step", {
                template : "<awc-daily-status></awc-daily-status>",
            })
            .when("/awcs_covered", {
                redirectTo : "/awcs_covered/map",
            })
            .when("/awcs_covered/:step", {
                template : "<awcs-covered></awcs-covered>",
            })
            .when("/registered_household", {
                redirectTo : "/registered_household/map",
            })
            .when("/registered_household/:step", {
                template : "<registered-household></registered-household>",
            })
            .when("/enrolled_children", {
                redirectTo : "/enrolled_children/map",
            })
            .when("/enrolled_children/:step", {
                template : "<enrolled-children></enrolled-children>",
            })
            .when("/enrolled_women", {
                redirectTo : "/enrolled_women/map",
            })
            .when("/enrolled_women/:step", {
                template : "<enrolled-women></enrolled-women>",
            })
            .when("/lactating_enrolled_women", {
                redirectTo : "/lactating_enrolled_women/map",
            })
            .when("/lactating_enrolled_women/:step", {
                template : "<lactating-enrolled-women></lactating-enrolled-women>",
            })
            .when("/adolescent_girls", {
                redirectTo : "/adolescent_girls/map",
            })
            .when("/adolescent_girls/:step", {
                template : "<adolescent-girls></adolescent-girls>",
            })
            .when("/adhaar", {
                redirectTo : "/adhaar/map",
            })
            .when("/adhaar/:step", {
                template : "<adhaar-beneficiary></adhaar-beneficiary>",
            })
            .when("/clean_water", {
                redirectTo : "/clean_water/map",
            })
            .when("/clean_water/:step", {
                template : "<clean-water></clean-water>",
            })
            .when("/functional_toilet", {
                redirectTo : "/functional_toilet/map",
            })
            .when("/functional_toilet/:step", {
                template : "<functional-toilet></functional-toilet>",
            })
            .when("/medicine_kit", {
                redirectTo : "/medicine_kit/map",
            })
            .when("/medicine_kit/:step", {
                template : "<medicine-kit></medicine-kit>",
            })
            .when("/infants_weight_scale", {
                redirectTo : "/infants_weight_scale/map",
            })
            .when("/infants_weight_scale/:step", {
                template : "<infants-weight-scale></infants-weight-scale>",
            })
            .when("/adult_weight_scale", {
                redirectTo : "/adult_weight_scale/map",
            })
            .when("/adult_weight_scale/:step", {
                template : "<adult-weight-scale></adult-weight-scale>",
            });
    }]);

