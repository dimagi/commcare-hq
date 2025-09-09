import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";
import tabular from "reports/js/bootstrap3/tabular";

$(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
    $(".datatable[data-slug]").each(function () {
        tabular.renderPage(data.slug, initialPageData.get("report_table_js_options"));
    });
});
