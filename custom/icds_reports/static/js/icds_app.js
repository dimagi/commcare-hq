function MainController($scope, $route, $routeParams, $location, $rootScope) {
    $scope.$route = $route;
    $scope.$location = $location;
    $scope.$routeParams = $routeParams;
    $scope.systemUsageCollapsed = true;
    $scope.healthCollapsed = true;
}

MainController.$inject = ['$scope', '$route', '$routeParams', '$location'];

window.angular.module('icdsApp', ['ngRoute', 'ui.select', 'ngSanitize', 'datamaps', 'ui.bootstrap', 'nvd3', 'datatables', 'datatables.bootstrap', 'leaflet-directive', 'cgBusy'])
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
            .when("/stunning", {
                redirectTo : "/stunning/map",
            })
            .when("/stunning/:step", {
                template : "<prevalence-of-stunning></prevalence-of-stunning>",
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
            .when("/progress_report", {
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
            });
    }]);

