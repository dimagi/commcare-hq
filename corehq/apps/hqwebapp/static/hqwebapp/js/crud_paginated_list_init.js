hqDefine("hqwebapp/js/crud_paginated_list_init", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/crud_paginated_list",
], function(
    $,
    ko,
    initialPageData,
    CRUDPaginatedList
) {
    $(function () {
        var paginatedListModel = CRUDPaginatedList.CRUDPaginatedListModel(
            initialPageData.get('total'),
            initialPageData.get('limit'),
            initialPageData.get('page'),
            {
                statusCodeText: initialPageData.get('status_codes'),
                allowItemCreation: initialPageData.get('allow_item_creation'),
                createItemForm: initialPageData.get('create_item_form'),
            }
        );

        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
    });
});
