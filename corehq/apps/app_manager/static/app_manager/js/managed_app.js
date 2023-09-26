hqDefine("app_manager/js/managed_app", function () {
    $(function () {
        var initial_page_data = hqImport('hqwebapp/js/initial_page_data').get,
            init = hqImport('app_manager/js/app_manager').init,
            app = initial_page_data('app_subset');

        init({
            appVersion: app.version || -1,
            commcareVersion: String(app.commcare_minor_release),
            latestCommcareVersion: initial_page_data('latest_commcare_version') || null,
        });

        $('.btn-langcode-preprocessed').each(function () {
            hqImport('hqwebapp/js/bootstrap3/ui-element').langcode_tag_btn($(this), $(this).text());
            if ($(this).hasClass('langcode-input')) {
                var $langcodeInput = $(this).parent().find("input");
                var that = this;
                if ($langcodeInput) {
                    $langcodeInput.change(function () {
                        if ($(this).val() == "")
                            $(that).show();
                        else
                            $(that).hide();
                    });
                }
            }
        });

        $('[data-toggle="tooltip"]').tooltip();

        // https://github.com/twitter/bootstrap/issues/6122
        // this is necessary to get popovers to be able to extend
        // outside the borders of their containing div
        //
        // http://manage.dimagi.com/default.asp?183618
        // Firefox 40 considers hovering on a select a mouseleave event and thus kills the select
        // dropdown. The focus and blur events are to ensure that we do not trigger overflow hidden
        // if we are in a select
        var inSelectElement = false,
            $tabContent = $('.tab-content');
        $tabContent.css('overflow', 'visible');
        $tabContent.on('mouseenter', '.collapse', function () {
            $(this).css('overflow','visible');
        });
        $tabContent.on('mouseleave', '.collapse', function () {
            if (inSelectElement) { return; }
            $(this).css('overflow','hidden');
        });
        $tabContent.on('focus', '.collapse', function () {
            inSelectElement = true;
        });
        $tabContent.on('blur', '.collapse', function () {
            inSelectElement = false;
        });
    });
});
