/* global d3, moment */

var url = hqImport('hqwebapp/js/initial_page_data').reverse;

function MainController($scope, $route, $routeParams, $location, $uibModal, $window, $http, reportAnIssueUrl, isWebUser,
                        userLocationId, isAlertActive, haveAccessToFeatures) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
    $scope.isWebUser = isWebUser;
    $scope.dateChanged = false;
    $scope.haveAccessToFeatures = haveAccessToFeatures;

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

    $scope.reportAnIssue = function () {
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

    $scope.checkAccessToLocation = function () {
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

    $scope.isOlderThanAWeek = (function () {
        $http.get(url('release_date')).then(function (response) {
            if (response && response.data) {
                return response.data['isOlderThanAWeek'];
            }
            return true;
        });
    })();

    $scope.$on('$routeChangeStart', function () {
        $scope.checkAccessToLocation();
        var path = window.location.pathname + $location.path().substr(1);
        $window.ga('set', 'page', path);
        $window.ga('send', 'pageview', path);
    });

    // hack to have the same width between origin table and fixture headers,
    // without this fixture headers are bigger and not align to original columns
    var observer = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            if (mutation.addedNodes && mutation.addedNodes.length > 0) {
                var hasClass = [].some.call(mutation.addedNodes, function (el) {
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
    'haveAccessToFeatures',
];

window.angular.module('icdsApp', [
    'ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap', 'nvd3',
    'datatables', 'datatables.bootstrap', 'datatables.fixedcolumns', 'datatables.fixedheader',
    'leaflet-directive', 'cgBusy', 'perfect_scrollbar'])
    .controller('MainController', MainController)
    .config(['$interpolateProvider', '$routeProvider', function ($interpolateProvider, $routeProvider) {
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
            .when("/lady_supervisor", {
                template: "<lady-supervisor></lady-supervisor>",
            })
            .when("/download", {
                template: "<download></download>",
            })
            .when("/cas_export", {
                template: "<cas-export></cas-export>",
            })
            .when("/access_denied", {
                template: "<access-denied></access-denied>",
            });
        utils.addSharedRoutes($routeProvider, 'map');
    }]);

