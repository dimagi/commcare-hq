hqDefine("inddex/js/main", [
    'jquery',
    'reports/js/bootstrap3/tabular',
    'commcarehq',
], function (
    $,
    tabular,
) {
    $(document).on('ajaxSuccess', function (e, xhr, ajaxOptions, data) {
        $(".datatable[data-slug]").each(function (index, table) {
            const tableData = $(table).data();
            tabular.renderPage(data.slug, data.js_options);
        });
    });
});
