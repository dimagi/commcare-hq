hqDefine("reports/js/bootstrap5/readable_form", ["jquery"], function ($) {
    function showReadable() {
        $('.form-data-raw').hide();
        $('.form-data-readable').show();
    }

    function showRaw() {
        $('.form-data-readable').hide();
        $('.form-data-raw').show();
    }

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

    function attachEvents() {
        $(document).on('click', '.showReadable', showReadable);
        $(document).on('click', '.showRaw', showRaw);

        $(document).on('click', '.formDisplayToggle a', function () {
            // activate the correct 'tab' header
            $(this).tab('show');
            return false;
        });

        $(document).on('change', '.showSkippedToggle', function () {
            showSkipped($(this).is(':checked'));
        });
    }

    function init() {
        $('.showSkippedToggle').each(function () {
            if (!$('.form-data-skipped').length) {
                $(this).parent('label').hide();
            }
        });
        showReadable();
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
