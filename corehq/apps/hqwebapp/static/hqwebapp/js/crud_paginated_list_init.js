hqDefine("hqwebapp/js/crud_paginated_list_init", function() {
    $(function () {
        var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get,
            paginatedListModel = hqImport("hqwebapp/js/crud_paginated_list").CRUDPaginatedListModel(
                initial_page_data('total'),
                initial_page_data('limit'),
                initial_page_data('page'),
                {
                    statusCodeText: initial_page_data('status_codes'),
                    allowItemCreation: initial_page_data('allow_item_creation'),
                    createItemForm: initial_page_data('create_item_form'),
                }
            );

        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
    });
});
