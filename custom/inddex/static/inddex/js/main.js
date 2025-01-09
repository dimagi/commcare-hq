hqDefine("inddex/js/main", function () {
    const initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        tabular = hqImport("reports/js/bootstrap3/tabular");
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
        $(".datatable[data-slug]").each(function (index, table) {
            const tableData = $(table).data();
            tabular.renderPage(data.slug, initialPageData.get("report_table_js_options"));
        });
    });
});
