hqDefine("cloudcare/js/preview_app/main", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        previewApp = hqImport("cloudcare/js/preview_app/preview_app"),
        sentry = hqImport("cloudcare/js/sentry");

    $(function () {
        sentry.initSentry();

        window.MAPBOX_ACCESS_TOKEN = initialPageData.get('mapbox_access_token'); // maps api is loaded on-demand
        previewApp.start({
            apps: [initialPageData.get('app')],
            language: initialPageData.get('language'),
            username: initialPageData.get('username'),
            domain: initialPageData.get('domain'),
            formplayer_url: initialPageData.get('formplayer_url'),
            singleAppMode: true,
            phoneMode: true,
            oneQuestionPerScreen: !initialPageData.get('is_dimagi'),
            allowedHost: initialPageData.get('allowed_host'),
            environment: initialPageData.get('environment'),
            debuggerEnabled: initialPageData.get('debugger_enabled'),
        });

        $('.dragscroll').on('scroll', function () {
            $('.form-control').blur();
        });

        // Adjust for those pesky scrollbars
        _.each($('.scrollable-container'), function (sc) {
            var scrollWidth = $(sc).prop('offsetWidth') - $(sc).prop('clientWidth');
            $(sc).addClass('has-scrollbar-' + scrollWidth);
        });

        if (initialPageData("exceeds_mobile_ucr_threshold")) {
            previewApp.trigger(
                'showError',
                gettext("You have the MOBILE_UCR feature flag enabled, and have exceeded the maximum limit of 300 user configurable reports.")
            );
            // disable everything
            $('#single-app-view').find("*").prop('disabled', true);
        }
    });
});
