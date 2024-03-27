'use strict';

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

    var ApiKeyListModel = function (showAPIKeys, maximumKeyExpirationWindow) {

        var KeyModel = function (itemSpec, initRow) {
            return CRUDPaginatedList.PaginatedItem(itemSpec, function (rowElems, key) {
                initRow(rowElems, key);

                if (showAPIKeys) {
                    $(rowElems).find("button").click(function () {
                        navigator.clipboard.writeText(key.itemData().full_key);
                    });
                }
            });
        };

        var self = CRUDPaginatedList.CRUDPaginatedListModel(
            initialPageData.get('total'),
            initialPageData.get('limit'),
            initialPageData.get('page'),
            {
                statusCodeText: initialPageData.get('status_codes'),
                allowItemCreation: initialPageData.get('allow_item_creation'),
                createItemForm: initialPageData.get('create_item_form'),
                createItemFormClass: initialPageData.get('create_item_form_class'),
            }, KeyModel
        );

        self.createItemForm.subscribe(function () {
            // calling widgets.init() directly doesn't seem to create a new date picker,
            // so we have to delay the call
            setTimeout(self.initDatePicker);
        });

        self.initDatePicker = function () {
            let options = { dateFormat: 'yy-mm-dd', minDate: new Date() };
            if (maximumKeyExpirationWindow) {
                options['maxDate'] = maximumKeyExpirationWindow;
            }
            $('.date-picker').datepicker(options);
        };

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
        const showAPIKeys = initialPageData.get('always_show_user_api_keys');
        const maximumKeyExpirationWindow = initialPageData.get('maximum_key_expiration_window');
        var paginatedListModel = ApiKeyListModel(showAPIKeys, maximumKeyExpirationWindow);
        ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
        paginatedListModel.init();
        paginatedListModel.initDatePicker();
        widgets.init();
    });

    return 1;
});
