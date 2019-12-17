/* global angular */

hqDefine("js/icds_dashboard_utils", function () {
    function populateDashboardConstants(appName) {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data");
        angular.module(appName).constant('isAlertActive', window.angular.element('.alert-maintenance').children().length === 1);
        angular.module(appName).constant('isMobile', initialPageData.get("is_mobile"));
        angular.module(appName).constant('locationHierarchy', initialPageData.get("location_hierarchy"));
        angular.module(appName).constant('userLocationId', initialPageData.get("user_location_id"));
        angular.module(appName).constant('userLocationType', initialPageData.get("user_location_type"));
        angular.module(appName).constant('allUserLocationId', initialPageData.get("all_user_location_id"));
        angular.module(appName).constant('reportAnIssueUrl', initialPageData.get("report_an_issue_url"));
        angular.module(appName).constant('isWebUser', initialPageData.get("is_web_user"));
        angular.module(appName).constant('haveAccessToFeatures', initialPageData.get("have_access_to_features"));
        angular.module(appName).constant('haveAccessToAllLocations', initialPageData.get("have_access_to_all_locations"));
        angular.module(appName).constant('stateLevelAccess', initialPageData.get("state_level_access"));
        angular.module(appName).constant('navMetadata', initialPageData.get("nav_metadata"));
        angular.module(appName).constant('userFullName', initialPageData.get("user_full_name"));
        angular.module(appName).constant('userUsername', initialPageData.get("user_username"));
        angular.module(appName).constant('genders', [
            {id: '', name: 'All'},
            {id: 'M', name: 'Male'},
            {id: 'F', name: 'Female'},
        ]);
        angular.module(appName).constant('ages', [
            {id: '', name: 'All'},
            {id: '6', name: '0-6 months (0-180 days)'},
            {id: '12', name: '6-12 months (181-365 days)'},
            {id: '24', name: '12-24 months (366-730 days)'},
            {id: '36', name: '24-36 months (731-1095 days)'},
            {id: '48', name: '36-48 months (1096-1460 days)'},
            {id: '60', name: '48-60 months (1461-1825 days)'},
            {id: '72', name: '60-72 months (1826-2190 days)'},
        ]);
        angular.module(appName).constant('agesServiceDeliveryDashboard', [
            {id: '0_3', name: 'PW, LW & Children 0-3 years (0-1095 days)'},
            {id: '3_6', name: 'Children 3-6 years (1096-2190 days)'},
        ]);
        angular.module(appName).constant('mobileMapsEnabled', initialPageData.get("mobile_maps_enabled"));
    }

    function addMaternalChildRoutes($routeProvider, defaultStep) {
        return $routeProvider.when("/maternal_and_child", {
                redirectTo: "/maternal_and_child/underweight_children/" + defaultStep,
            })
            .when("/maternal_and_child/underweight_children", {
                redirectTo: "/maternal_and_child/underweight_children/" + defaultStep,
            })
            .when("/maternal_and_child/underweight_children/:step", {
                template: "<underweight-children-report></underweight-children-report>",
            })
            .when("/maternal_and_child/wasting", {
                redirectTo: "/maternal_and_child/wasting/" + defaultStep,
            })
            .when("/maternal_and_child/wasting/:step", {
                template: "<prevalence-of-severe></prevalence-of-severe>",
            })
            .when("/maternal_and_child/stunting", {
                redirectTo: "/maternal_and_child/stunting/" + defaultStep,
            })
            .when("/maternal_and_child/stunting/:step", {
                template: "<prevalence-of-stunting></prevalence-of-stunting>",
            })
            .when("/maternal_and_child/low_birth", {
                redirectTo: "/maternal_and_child/low_birth/" + defaultStep,
            })
            .when("/maternal_and_child/low_birth/:step", {
                template: "<newborn-low-weight></newborn-low-weight>",
            })
            .when("/maternal_and_child/early_initiation", {
                redirectTo: "/maternal_and_child/early_initiation/" + defaultStep,
            })
            .when("/maternal_and_child/early_initiation/:step", {
                template: "<early-initiation-breastfeeding></early-initiation-breastfeeding>",
            })
            .when("/maternal_and_child/exclusive_breastfeeding", {
                redirectTo: "/maternal_and_child/exclusive_breastfeeding/" + defaultStep,
            })
            .when("/maternal_and_child/exclusive_breastfeeding/:step", {
                template: "<exclusive-breastfeeding></exclusive-breastfeeding>",
            })
            .when("/maternal_and_child/children_initiated", {
                redirectTo: "/maternal_and_child/children_initiated/" + defaultStep,
            })
            .when("/maternal_and_child/children_initiated/:step", {
                template: "<children-initiated></children-initiated>",
            })
            .when("/maternal_and_child/institutional_deliveries", {
                redirectTo: "/maternal_and_child/institutional_deliveries/" + defaultStep,
            })
            .when("/maternal_and_child/institutional_deliveries/:step", {
                template: "<institutional-deliveries></institutional-deliveries>",
            })
            .when("/maternal_and_child/immunization_coverage", {
                redirectTo: "/maternal_and_child/immunization_coverage/" + defaultStep,
            })
            .when("/maternal_and_child/immunization_coverage/:step", {
                template: "<immunization-coverage></immunization-coverage>",
            });
    }
    function addCasReachRoutes($routeProvider, defaultStep) {
        return $routeProvider.when("/icds_cas_reach", {
                redirectTo: "/icds_cas_reach/awc_daily_status/" + defaultStep,
            })
            .when("/icds_cas_reach/awc_daily_status", {
                redirectTo: "/icds_cas_reach/awc_daily_status/" + defaultStep,
            })
            .when("/icds_cas_reach/awc_daily_status/:step", {
                template: "<awc-daily-status></awc-daily-status>",
            })
            .when("/icds_cas_reach/awcs_covered", {
                redirectTo: "/icds_cas_reach/awcs_covered/" + defaultStep,
            })
            .when("/icds_cas_reach/awcs_covered/:step", {
                template: "<awcs-covered></awcs-covered>",
            });
    }
    function addAWCReportRoutes($routeProvider) {
        $routeProvider.when("/awc_reports", {
                redirectTo: "/awc_reports/pse",
            })
            .when("/awc_reports/:step", {
                template: "<awc-reports></awc-reports>",
            });
    }
    function addSharedRoutes($routeProvider, defaultStep) {
        addMaternalChildRoutes($routeProvider, defaultStep);
        addCasReachRoutes($routeProvider, defaultStep);
        addAWCReportRoutes($routeProvider);
    }
    return {
        populateDashboardConstants: populateDashboardConstants,
        addMaternalChildRoutes: addMaternalChildRoutes,
        addCasReachRoutes: addCasReachRoutes,
        addAWCReportRoutes: addAWCReportRoutes,
        addSharedRoutes: addSharedRoutes,
    };
});
