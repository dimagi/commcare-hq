'use strict';

hqDefine("settings/js/user_api_keys", [
    "jquery",
    "knockout",
    "underscore",
    "moment",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap5/crud_paginated_list",
    "hqwebapp/js/tempus_dominus",
    "commcarehq",
], function (
    $,
    ko,
    _,
    moment,
    initialPageData,
    CRUDPaginatedList,
    hqTempusDominus
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
            hqTempusDominus.createDatePicker($('.date-picker').get(0), {
                restrictions: {
                    minDate: new Date(),
                    maxDate: maximumKeyExpirationWindow ? moment().add(maximumKeyExpirationWindow, 'days').toDate() : undefined,
                }
            });
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
    });

    return 1;
});
