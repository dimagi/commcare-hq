hqDefine('domain/js/bootstrap5/case_search_main', [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'domain/js/bootstrap5/case_search',
    'hqwebapp/js/bootstrap5/knockout_bindings.ko',     // save button
], function (
    $,
    initialPageData,
    caseSearch
) {
    $(function () {
        var viewModel = caseSearch.caseSearchConfig({
            values: initialPageData.get('values'),
            caseTypes: initialPageData.get('case_types'),
        });
        $('#case-search-config').koApplyBindings(viewModel);
        $('#case-search-config').on('change', viewModel.change).on('click', ':button', viewModel.change);
    });
});
