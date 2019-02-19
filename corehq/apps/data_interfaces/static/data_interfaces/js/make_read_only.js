hqDefine("data_interfaces/js/make_read_only",[
    'jquery',
    'hqwebapp/js/initial_page_data',
], function ($,initialPageData) {

    $(function () {
        if (initialPageData.get('read_only_mode')) {
            $('.main-form :input').prop('disabled', true);
        }
    });

});
