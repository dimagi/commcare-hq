/* global d3, moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MainController($scope, $route, $routeParams, $location, $uibModal, $window, $http, reportAnIssueUrl, isWebUser, userLocationId, isAlertActive) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.isWebUser = isWebUser;
    $scope.dateChanged = false;

    angular.element(document).ready(function () {
        $scope.adjustUIComponentsIfAlertIsActive();
    });

    function fixEscapedURLAmpersands() {
        // if the URL has replaced any "&" characters with "&amp;" then this will fix the
        // associated parameter keys.
        var locationParams = $location.search();
        var newKey;
        for (var key in locationParams) {
            newKey = key;
            if (newKey.startsWith('amp;')) {
                newKey = newKey.slice(4);
                $location.search(newKey, locationParams[key]).search(key, null);
            }
        }

    }
    fixEscapedURLAmpersands();

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

    $scope.adjustUIComponentsIfAlertIsActive = function () {
        // 'fixes-filters'
        if (isAlertActive) {
            var elementsToUpdate = ['left-menu', 'fixed-title', 'main-container'];
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
    'isAlertActive',
];

window.angular.module('icdsApp', [
        'ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap', 'nvd3',
        'datatables', 'datatables.bootstrap', 'datatables.fixedcolumns', 'datatables.fixedheader',
        'leaflet-directive', 'cgBusy', 'perfect_scrollbar'])
    .controller('MainController', MainController)
    .config(['$interpolateProvider', '$routeProvider', function($interpolateProvider, $routeProvider) {
        var utils = hqImport("js/icds_dashboard_utils");
        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');
        $routeProvider
            .when("/", {
                redirectTo: '/program_summary/maternal_child',
            }).when("/program_summary/:step", {
                template: "<program-summary></program-summary>",
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
            .when("/awc_infrastructure/infantometer", {
                redirectTo: "/awc_infrastructure/infantometer/map",
            })
            .when("/awc_infrastructure/infantometer/:step", {
                template: "<infantometer></infantometer>",
            })
            .when("/awc_infrastructure/stadiometer", {
                redirectTo: "/awc_infrastructure/stadiometer/map",
            })
            .when("/awc_infrastructure/stadiometer/:step", {
                template: "<stadiometer></stadiometer>",
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
            .when("/service_delivery_dashboard", {
                redirectTo: "/service_delivery_dashboard/pw_lw_children",
            })
            .when("/service_delivery_dashboard/:step", {
                template: "<service-delivery-dashboard></service-delivery-dashboard>",
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
        utils.addSharedRoutes($routeProvider, 'map');
    }]);

