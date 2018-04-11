hqDefine("hqpillow_retry/js/pillow_errors", function() {
    $(function() {
        $(document).on('click', '#check_all', function() {
            var oTable = $('#report_table_' + hqImport('hqwebapp/js/initial_page_data').get('slug')).dataTable();
            $('input', oTable.fnGetNodes()).prop('checked', this.checked);
        });
    });
});
