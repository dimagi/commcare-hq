hqDefine("cloudcare/js/preview_app/main", function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data"),
        previewApp = hqImport("cloudcare/js/preview_app/preview_app"),
        utils = hqImport("cloudcare/js/utils"),
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

        utils.injectMarkdownAnchorTransforms();

        $('.dragscroll').on('scroll', function () {
            $('.form-control').blur();
        });

        // Adjust for those pesky scrollbars
        _.each($('.scrollable-container'), function (sc) {
            var scrollWidth = $(sc).prop('offsetWidth') - $(sc).prop('clientWidth');
            $(sc).addClass('has-scrollbar-' + scrollWidth);
        });
    });
});
