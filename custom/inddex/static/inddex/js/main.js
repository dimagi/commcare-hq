hqDefine("inddex/js/main", function () {
    const tabular = hqImport("reports/js/bootstrap3/tabular");
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
        $(".datatable[data-slug]").each(function (index, table) {
            const tableData = $(table).data();
            tabular.renderPage(data.slug, data.js_options);
        });
    });
});
