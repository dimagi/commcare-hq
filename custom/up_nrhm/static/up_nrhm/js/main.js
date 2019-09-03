hqDefine("up_nrhm/js/main", function () {
    function hideFilters(sf) {
        if (sf === "" || sf === 'sf2') {
            $('#fieldset_datespan').css('display', 'block');
            $('#fieldset_year').css('display', 'none');
            $('#fieldset_month').css('display', 'none');
            $('#report_filter_hierarchy_af').parent().parent().removeClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf3") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().removeClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf4") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().addClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().removeClass('hideImportant');
        } else if (sf === "sf5") {
            $('#fieldset_datespan').css('display', 'none');
            $('#fieldset_year').css('display', 'block');
            $('#fieldset_month').css('display', 'block');
            $('#report_filter_hierarchy_af').parent().parent().addClass('hideImportant');
            $('#report_filter_hierarchy_block').parent().parent().addClass('hideImportant');
        }
    }

    $(function () {
        $('#report_filter_sf').on('change', function() {
            sf = $(this).val();
            hideFilters(sf);
        });
        $('#hq-report-filters').on('change', function() {
            hideFilters(sf);
        });
        sf = $('#report_filter_sf').val();
        hideFilters(sf);
    });
});
