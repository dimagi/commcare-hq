hqDefine('case_importer/js/excel_config', function() {
    $(function() {
        $('#back_button').click(function() {
            history.back();
            return false;
        });

        $('#back_breadcrumb').click(function(e) {
            e.preventDefault();
            history.back();
            return false;
        });
    });
});
