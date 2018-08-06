hqDefine("data_interfaces/js/list_automatic_update_rules", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/crud_paginated_list',
    'analytix/js/google',
], function(
    $,
    ko,
    _,
    initialPageData,
    CRUDPaginatedList,
    googleAnalytics
) {
    var showActionError = function(rule, error) {
        var newItemData = _.extend({}, rule.itemData(), {
            action_error: error,
        });
        rule.itemData(newItemData);
    };

    var updateRule = function(action, rule) {
        $.ajax({
            url: "",
            type: "POST",
            dataType: 'json',
            data: {
                action: action,
                id: rule.itemId,
            },
            success: function(data) {
                if (data.success) {
                    rule.itemData(data.itemData);
                } else {
                    showActionError(rule, data.error);
                }
            },
            error: function() {
                showActionError(rule, gettext("Issue communicating with server. Try again."));
            },
        });
    };

    var ruleModel = function(itemSpec, initRow) {
        return CRUDPaginatedList.PaginatedItem(itemSpec, function(rowElems, rule) {
            initRow(rowElems, rule);

            $(rowElems).find("button[data-action]").click(function() {
                updateRule($(this).data("action"), rule);
            });
        });
    };

    $(function () {
        var paginatedListModel = CRUDPaginatedList.CRUDPaginatedListModel(
            initialPageData.get('total'),
            initialPageData.get('limit'),
            initialPageData.get('page'), {
                statusCodeText: initialPageData.get('status_codes'),
                allowItemCreation: initialPageData.get('allow_item_creation'),
                createItemForm: initialPageData.get('create_item_form'),
            }, ruleModel);

        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();

        $("#add-new").click(function() {
            googleAnalytics.track.event('Automatic Case Closure', 'Rules', 'Set Rule');
        });
    });
    /*'use strict';
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
    });*/
});
