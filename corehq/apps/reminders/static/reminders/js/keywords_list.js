import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import initialPageData from "hqwebapp/js/initial_page_data";
import CRUDPaginatedList from "hqwebapp/js/bootstrap5/crud_paginated_list";

$(function () {
    var paginatedListModel = CRUDPaginatedList.CRUDPaginatedListModel(
        initialPageData.get('total'),
        initialPageData.get('limit'),
        initialPageData.get('page'), {
            statusCodeText: initialPageData.get('status_codes'),
            allowItemCreation: initialPageData.get('allow_item_creation'),
            createItemForm: initialPageData.get('create_item_form'),
        });

    paginatedListModel.hasLinkedModels = initialPageData.get('has_linked_data');
    paginatedListModel.allowEdit = initialPageData.get('can_edit_linked_data');

    paginatedListModel.unlockLinkedData = ko.observable(false);
    paginatedListModel.toggleLinkedLock = function () {
        paginatedListModel.unlockLinkedData(!paginatedListModel.unlockLinkedData());
    };

    $('#editable-paginated-list').koApplyBindings(paginatedListModel);
    $('#lock-container').koApplyBindings(paginatedListModel);
    $('#edit-warning-modal').koApplyBindings(paginatedListModel);
    paginatedListModel.init();


});
