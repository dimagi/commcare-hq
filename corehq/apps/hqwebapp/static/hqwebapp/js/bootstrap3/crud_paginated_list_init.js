hqDefine("hqwebapp/js/bootstrap3/crud_paginated_list_init", [
    "jquery",
    "knockout",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/crud_paginated_list",
], function (
    $,
    ko,
    initialPageData,
    CRUDPaginatedList
) {
    var paginatedListModel = CRUDPaginatedList.CRUDPaginatedListModel(
        initialPageData.get('total'),
        initialPageData.get('limit'),
        initialPageData.get('page'),
        {
            statusCodeText: initialPageData.get('status_codes'),
            allowItemCreation: initialPageData.get('allow_item_creation'),
            createItemForm: initialPageData.get('create_item_form'),
            createItemFormClass: initialPageData.get('create_item_form_class'),
        }
    );

    $(function () {
        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
    });

    return {'paginatedListModel': paginatedListModel};
});
