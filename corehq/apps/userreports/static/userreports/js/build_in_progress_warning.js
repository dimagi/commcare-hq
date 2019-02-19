hqDefine("userreports/js/build_in_progress_warning", function () {
    var initial_page_data = hqImport("hqwebapp/js/initial_page_data").get;

    if (!initial_page_data("is_static_data_source")) {
        var retrying = false;
        (function poll() {
            $.ajax({
                url: hqImport("hqwebapp/js/initial_page_data").reverse('configurable_data_source_status'),
                dataType: 'json',
                success: function (data) {
                    if (data.isBuilt) {
                        $('#built-warning').addClass('hide');
                        if (retrying) {
                            location.reload();
                        } else if ($('#report-filters').find('.control-label').length === 0) {
                            $('#report-filters').submit();
                        }
                    } else {
                        retrying = true;
                        $('#built-warning').removeClass('hide');
                        setTimeout(poll, 5000);
                    }
                },
            });
        })();
    }
});
