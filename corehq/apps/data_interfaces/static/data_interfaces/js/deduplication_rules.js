hqDefine("data_interfaces/js/deduplication_rules", [
    'jquery',
    'knockout',
    'underscore',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/bootstrap3/crud_paginated_list',
    'analytix/js/google',
], function (
    $,
    ko,
    _,
    initialPageData,
    CRUDPaginatedList,
    googleAnalytics
) {
    var showActionError = function (rule, error) {
        var newItemData = _.extend({}, rule.itemData(), {
            action_error: error,
        });
        rule.updateItemSpec({itemData: newItemData});
    };

    var updateRule = function (action, rule) {
        $.ajax({
            url: "",
            type: "POST",
            dataType: 'json',
            data: {
                action: action,
                id: rule.itemId,
            },
            success: function (data) {
                if (data.success) {
                    rule.itemData(data.itemData);
                } else {
                    showActionError(rule, data.error);
                }
            },
            error: function () {
                showActionError(rule, gettext("Issue communicating with server. Try again."));
            },
        });
    };

    var ruleModel = function (itemSpec, initRow) {
        return CRUDPaginatedList.PaginatedItem(itemSpec, function (rowElems, rule) {
            initRow(rowElems, rule);

            $(rowElems).find("button[data-action]").click(function () {
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

        $("#add-new").click(function () {
            googleAnalytics.track.event('Automatic Case Closure', 'Rules', 'Set Rule');
        });
    });
});
