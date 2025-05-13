import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import CRUDPaginatedList from "hqwebapp/js/bootstrap3/crud_paginated_list";

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
);

$(function () {
    ko.applyBindings(paginatedListModel, $('#editable-paginated-list').get(0));
    paginatedListModel.init();
});

export default {'paginatedListModel': paginatedListModel};
