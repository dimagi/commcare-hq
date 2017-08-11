/* globals COMMCAREHQ, hqLayout */
hqDefine("app_manager/js/summary/summary", function() {
    $(function() {
        'use strict';

        var v2 = !COMMCAREHQ.toggleEnabled('APP_MANAGER_V1');
        if (v2) {
            hqLayout.utils.setIsAppbuilderResizing(true);
        }

        var summaryApp = window.angular.module('summaryApp', ['ngRoute', 'summaryModule']),
            initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            url = hqImport('hqwebapp/js/urllib').reverse;
        summaryApp.config(['$httpProvider', function($httpProvider) {
            $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
            $httpProvider.defaults.xsrfCookieName = 'csrftoken';
            $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
            $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
        }]);
        summaryApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
            djangoRMIProvider.configure(initial_page_data('djng_current_rmi'));
        }]);

        summaryApp.constant('summaryConfig', {
            staticRoot: initial_page_data('static_root'),
            vellumTypes: initial_page_data('vellum_types'),
            formNameMap: initial_page_data('form_name_map'),
            appLangs: initial_page_data('app_langs'),
            caseDownloadURL: url("download_case_summary"),
            formDownloadURL: url("download_form_summary"),
            appDownloadURL: url("download_app_summary"),
            appSettingsURL: url("release_manager"),
            appHomeURL: url("view_app"),
            appName: initial_page_data("app_name"),
        });

        summaryApp.config(['$routeProvider', function($routeProvider) {
            $routeProvider.
                when('/forms', {
                    templateUrl: url("ng_template", "form_summary_view" + (v2 ? "_v2" : "")),
                    controller: 'FormController',
                }).
                when('/cases', {
                    templateUrl: url("ng_template", "case_summary_view" + (v2 ? "_v2" : "")),
                    controller: 'CaseController',
                }).
                otherwise({
                    redirectTo: '/forms',
                });
        }]);

        window.angular.bootstrap(document.getElementById("summary-app"), ["summaryApp"]);
    });
});
