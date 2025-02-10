
hqDefine("reports/js/case_activity", ['jquery'], function ($) {

    $(document).ajaxSuccess(function (event, xhr, settings) {
        if (settings.url.match(/reports\/async\/case_activity/)) {
            const $specialNotice = $("#report-special-notice");
            if ($specialNotice) {
                const urlParams = new URLSearchParams(window.location.search);
                (urlParams.get('view_by') === 'groups') ? $specialNotice.show() : $specialNotice.hide();
            }
        }
    });
});