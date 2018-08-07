hqDefine("icds_reports/js/base", function() {
    $(function() {
        $(document).on('change', '#fieldset_location_async select', function(e) {
            e.stopPropagation();
            var state = $('select.form-control')[0].selectedIndex;
            var applyBtn = $('#apply-filters');
            if (state == 0) {
                applyBtn.disableButtonNoSpinner();
            } else {
                applyBtn.enableButton();
            }
        });
    });
});
