import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import caseSearch from "domain/js/bootstrap3/case_search";
import "hqwebapp/js/bootstrap3/knockout_bindings.ko";  // save button

$(function () {
    var viewModel = caseSearch.caseSearchConfig({
        values: initialPageData.get('values'),
        caseTypes: initialPageData.get('case_types'),
    });
    $('#case-search-config').koApplyBindings(viewModel);
    $('#case-search-config').on('change', viewModel.change).on('click', ':button', viewModel.change);
});
