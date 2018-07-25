hqDefine("icds_reports/js/base", function() {
    $(function() {
        $('#fieldset_location_async').on('change', 'select', function(e) {
            e.stopPropagation();
            var state = $('select.form-control')[0].selectedIndex;
            var applyBtn = $('#apply-filters');
            if (state == 0) {
                applyBtn.disableButtonNoSpinner();
            } else {
                applyBtn.enableButton();
            }
        })
    })
});
