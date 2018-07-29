hqDefine("data_interfaces/js/list_automatic_update_rules", function() {
    'use strict';
    var autoUpdateRuleApp = window.angular.module('autoUpdateRuleApp', ['hq.pagination']);
    autoUpdateRuleApp.config(['$httpProvider', function($httpProvider) {
        $httpProvider.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
        $httpProvider.defaults.headers.common["X-CSRFToken"] = $("#csrfTokenContainer").val();
    }]);

    autoUpdateRuleApp.config(["djangoRMIProvider", function(djangoRMIProvider) {
        djangoRMIProvider.configure(hqImport("hqwebapp/js/initial_page_data").get("djng_current_rmi"));
    }]);
    autoUpdateRuleApp.constant('paginationLimitCookieName', '{{ pagination_limit_cookie_name }}');
    autoUpdateRuleApp.constant('paginationCustomData', {
        activateRule: function (rule, djangoRMI) {
            djangoRMI.update_rule({
                id: rule.id,
                update_action: 'activate'
            })
            .success(function (data) {
                if (data.success) {
                    rule.active = true;
                    rule.action_error = '';
                } else {
                    rule.action_error = data.error;
                }
            })
            .error(function () {
                rule.action_error = gettext("Issue communicating with server. Try again.");
            });
        },
        deactivateRule: function (rule, djangoRMI) {
            djangoRMI.update_rule({
                id: rule.id,
                update_action: 'deactivate'
            })
            .success(function (data) {
                if (data.success) {
                    rule.active = false;
                    rule.action_error = '';
                } else {
                    rule.action_error = data.error;
                }
            })
            .error(function () {
                rule.action_error = gettext("Issue communicating with server. Try again.");
            });
        },
        deleteRule: function (rule, djangoRMI, paginationController) {
            $('#delete_' + rule.id).modal('hide');
            djangoRMI.update_rule({
                id: rule.id,
                update_action: 'delete'
            })
            .success(function (data) {
                if (data.success) {
                    rule.action_error = '';
                } else {
                    rule.action_error = data.error;
                }
                paginationController.getData();
            })
            .error(function () {
                rule.action_error = gettext("Issue communicating with server. Try again.");
            });
        },
        trackNewRule: function () {
            hqImport('analytix/js/google').track.event('Automatic Case Closure', 'Rules', 'Set Rule');
        },
    });
});
