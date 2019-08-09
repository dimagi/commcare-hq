hqDefine("icds_reports/js/base", function () {
    $(function () {
        $(document).on('change', '#fieldset_location_async select', function (e) {
            e.stopPropagation();
            var applyBtn = $('#apply-filters');
            var mprLocationInfo = $('#mpr-banner-info');
            var isMprReport = mprLocationInfo.length == 1;

            if (isMprReport) {
                var isSectorOrAWCSelected = $('select.form-control').length === 4;
                setTimeout(function () {
                    if (isSectorOrAWCSelected) {
                        applyBtn.enableButton();
                        mprLocationInfo.hide();
                    } else {
                        applyBtn.disableButtonNoSpinner();
                    }
                }, 0);
            } else {
                var state = $('select.form-control')[0].selectedIndex;
                if (state == 0) {
                    applyBtn.disableButtonNoSpinner();
                } else {
                    applyBtn.enableButton();
                }
            }

        });
    });
});
