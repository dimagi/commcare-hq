var B3PaginatedItem = function (itemSpec, initRow) {
    'use strict';
    ko.utils.extend(this, new PaginatedItem(itemSpec, initRow));

    this.dismissModals = function () {
        var $modals = this.getItemRow().find('.modal');
        if ($modals) {
            $modals.modal('hide');
            $('body').removeClass('modal-open');
            $('.modal-backdrop').remove(); //fix for b3
        }
    };
};



var B3CRUDPaginatedListModel = function (
    total,
    pageLimit,
    currentPage,
    options
) {
    'use strict';
    ko.utils.extend(this, new CRUDPaginatedListModel(total, pageLimit, currentPage, options, B3PaginatedItem));
};
