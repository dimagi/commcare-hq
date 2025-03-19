hqDefine("inddex/js/main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'reports/js/bootstrap3/tabular',
], function (
    $,
    initialPageData,
    tabular
) {
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
        $(".datatable[data-slug]").each(function (index, table) {
            tabular.renderPage(data.slug, initialPageData.get("report_table_js_options"));
        });
    });
});
