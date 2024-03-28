hqDefine("settings/js/bootstrap3/user_api_keys", [
    "jquery",
    "knockout",
    'underscore',
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/crud_paginated_list",
    'hqwebapp/js/bootstrap3/widgets',
], function (
    $,
    ko,
    _,
    initialPageData,
    CRUDPaginatedList,
    widgets
) {

    var ApiKeyListModel = function () {
        var self = CRUDPaginatedList.CRUDPaginatedListModel(
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

        var updateApiKey = function (action, apiKeyId) {
            $.ajax({
                url: "",
                type: "POST",
                dataType: 'json',
                data: {
                    action: action,
                    id: apiKeyId,
                },
                statusCode: self.handleStatusCode,
                success: function (data) {
                    var apiKey = _.find(self.paginatedList(), function (item) {
                        return item.itemId === apiKeyId;
                    });
                    apiKey.itemData(data.itemData);
                },
            });
        };
        self.deactivate = function (apiKey) {
            updateApiKey('deactivate', apiKey.id);
        };
        self.activate = function (apiKey) {
            updateApiKey('activate', apiKey.id);
        };
        return self;
    };

    $(function () {
        var paginatedListModel = ApiKeyListModel();
        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
        widgets.init();
    });

    return 1;
});
