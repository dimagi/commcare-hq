hqDefine("data_interfaces/js/make_read_only", function() {

    $(function() {
        if(hqImport("hqwebapp/js/initial_page_data").get('read_only_mode')) {
            $('.main-form :input').prop('disabled', true);
        }
    });

});
