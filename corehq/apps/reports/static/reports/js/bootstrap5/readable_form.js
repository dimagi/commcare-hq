hqDefine("reports/js/bootstrap5/readable_form", ["jquery"], function ($) {
    function showReadable(show) {
        if (show) {
            $('.form-data-raw').removeClass("d-none");
            $('.form-data-readable').addClass("d-none");
        } else {
            $('.form-data-raw').addClass("d-none");
            $('.form-data-readable').removeClass("d-none");
        }
    }

    function showSkipped(show) {
        if (show) {
            $('.form-data-skipped').removeClass("d-none");
            $('.form-data-skipped-spacer').addClass("d-none");
            $('.form-data-hidden-values').each(function () {
                $(this).removeClass("d-none");
            });
        } else {
            $('.form-data-skipped').addClass("d-none");
            $('.form-data-skipped-spacer').removeClass("d-none");
            $('.form-data-hidden-values').each(function () {
                var current = $(this).next();
                while (current.is('.form-data-question')) {
                    if (!current.is('.form-data-skipped')) {
                        return;
                    }
                    current = current.next();
                }
                $(this).addClass("d-none");
            });
        }
    }

    function attachEvents() {
        $(document).on('change', '#showReadable', function () {
            showReadable($(this).is(':checked'));
        });

        $(document).on('change', '#showSkippedToggle', function () {
            showSkipped($(this).is(':checked'));
        });
    }

    function init() {
        $('#showSkippedToggle').each(function () {
            if (!$('.form-data-skipped').length) {
                $(this).parent('label').addClass("d-none");
            }
        });
        showReadable(true);
        showSkipped(false);
    }

    $(function () {
        attachEvents();
        init();
    });

    return {
        init: init,
    };
});
