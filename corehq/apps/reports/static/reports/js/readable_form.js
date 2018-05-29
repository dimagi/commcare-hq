hqDefine("reports/js/readable_form", function() {
    $(function () {
        function showReadable() {
            $('.form-data-raw').hide();
            $('.form-data-readable').show();
        }
        function showRaw() {
            $('.form-data-readable').hide();
            $('.form-data-raw').show();
        }
        $('.showReadable').click(showReadable);
        $('.showRaw').click(showRaw);
        $('.formDisplayToggle a').click(function () {
            // activate the correct 'tab' header
            $(this).tab('show');
            return false;
        });

        // On page load, initially set show readable
        showReadable();

        function showSkipped(show) {
            if (show) {
                $('.form-data-skipped').show();
                $('.form-data-skipped-spacer').hide();
                $('.form-data-hidden-values').each(function () {
                    $(this).show();
                });
            } else {
                $('.form-data-skipped').hide();
                $('.form-data-skipped-spacer').show();
                $('.form-data-hidden-values').each(function () {
                    var current = $(this).next();
                    while (current.is('.form-data-question')) {
                        if (!current.is('.form-data-skipped')) {
                            return;
                        }
                        current = current.next();
                    }
                    $(this).hide();
                });
            }
        }
        $('.showSkippedToggle').change(function () {
            showSkipped($(this).is(':checked'));
        }).each(function () {
            if ($('.form-data-skipped').length == 0) {
                $(this).parent('label').hide();
            }
        });
        showSkipped(false);
    });
});
