hqDefine("settings/js/user_api_keys", [
    "jquery",
    "knockout",
    'underscore',
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/crud_paginated_list",
], function (
    $,
    ko,
    _,
    initialPageData,
    CRUDPaginatedList
) {

    var updateApiKey = function (action, apiKey) {
        $.ajax({
            url: "",
            type: "POST",
            dataType: 'json',
            data: {
                action: action,
                id: apiKey.itemId,
            },
            success: function (data) {
                apiKey.itemData(data.itemData);
            },
        });
    };

    var ApiKeyModel = function (itemSpec, initRow) {
        return CRUDPaginatedList.PaginatedItem(itemSpec, function (rowElems, apiKey) {
            initRow(rowElems, apiKey);

            $(rowElems).find("button[data-action]").click(function () {
                updateApiKey($(this).data("action"), apiKey);
            });
        });
    };

    var paginatedListModel = CRUDPaginatedList.CRUDPaginatedListModel(
        initialPageData.get('total'),
        initialPageData.get('limit'),
        initialPageData.get('page'),
        {
            statusCodeText: initialPageData.get('status_codes'),
            allowItemCreation: initialPageData.get('allow_item_creation'),
            createItemForm: initialPageData.get('create_item_form'),
            createItemFormClass: initialPageData.get('create_item_form_class'),
        },
        ApiKeyModel
    );

    $(function () {
        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
    });

    return {'paginatedListModel': paginatedListModel};
});
