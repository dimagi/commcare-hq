/* global angular hqImport */

function populateDashboardConstants() {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    angular.module('icdsApp').constant('isAlertActive', window.angular.element('.alert-maintenance').children().length === 1);
    angular.module('icdsApp').constant('locationHierarchy', initialPageData.get("location_hierarchy"));
    angular.module('icdsApp').constant('userLocationId', initialPageData.get("user_location_id"));
    angular.module('icdsApp').constant('allUserLocationId', initialPageData.get("all_user_location_id"));
    angular.module('icdsApp').constant('reportAnIssueUrl', initialPageData.get("report_an_issue_url"));
    angular.module('icdsApp').constant('isWebUser', initialPageData.get("is_web_user"));
    angular.module('icdsApp').constant('haveAccessToFeatures', initialPageData.get("have_access_to_features"));
    angular.module('icdsApp').constant('haveAccessToAllLocations', initialPageData.get("have_access_to_all_locations"));
    angular.module('icdsApp').constant('stateLevelAccess', initialPageData.get("state_level_access"));
    angular.module('icdsApp').constant('genders', [
        {id: '', name: 'All'},
        {id: 'M', name: 'Male'},
        {id: 'F', name: 'Female'},
    ]);
    angular.module('icdsApp').constant('ages', [
        {id: '', name: 'All'},
        {id: '6', name: '0-6 months (0-180 days)'},
        {id: '12', name: '6-12 months (181-365 days)'},
        {id: '24', name: '12-24 months (366-730 days)'},
        {id: '36', name: '24-36 months (731-1095 days)'},
        {id: '48', name: '36-48 months (1096-1460 days)'},
        {id: '60', name: '48-60 months (1461-1825 days)'},
        {id: '72', name: '60-72 months (1826-2190 days)'},
    ]);
    angular.module('icdsApp').constant('agesServiceDeliveryDashboard', [
        {id: '0_3', name: 'PW, LW & Children 0-3 years (0-1095 days)'},
        {id: '3_6', name: 'Children 3-6 years (1096-2190 days)'},
    ]);
}
