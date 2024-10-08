hqDefine('export/js/bootstrap5/incremental_export', [
    "jquery",
    "hqwebapp/js/initial_page_data",
    "hqwebapp/js/bootstrap5/crud_paginated_list_init",
], function ($, initialPageData, CRUDPaginatedListInit) {
    $(function () {
        var viewModel = CRUDPaginatedListInit.paginatedListModel;
        viewModel.reverse = initialPageData.reverse;
    });
});
