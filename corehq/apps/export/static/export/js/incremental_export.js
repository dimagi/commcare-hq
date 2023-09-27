hqDefine('export/js/incremental_export', [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap3/crud_paginated_list_init",
], function ($, initialPageData, CRUDPaginatedListInit) {
    $(function () {
        var viewModel = CRUDPaginatedListInit.paginatedListModel;
        viewModel.reverse = initialPageData.reverse;
    });
});
