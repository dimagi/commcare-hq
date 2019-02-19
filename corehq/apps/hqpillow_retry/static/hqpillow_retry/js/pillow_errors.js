hqDefine("hqpillow_retry/js/pillow_errors", function () {
    $(function () {
        $(document).on('click', '#check_all', function () {
            var slug = hqImport('hqwebapp/js/initial_page_data').get('slug'),
                oTable = $('#report_table_' + slug).dataTable();
            $('input', oTable.fnGetNodes()).prop('checked', this.checked);
        });
    });
});
