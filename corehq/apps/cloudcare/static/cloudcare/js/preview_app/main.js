hqDefine("cloudcare/js/preview_app/main", function () {
    $(function () {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        window.MAPBOX_ACCESS_TOKEN = initialPageData('mapbox_access_token'); // maps api is loaded on-demand
        hqImport('cloudcare/js/preview_app/preview_app').start({
            apps: [initialPageData('app')],
            language: initialPageData('language'),
            username: initialPageData('username'),
            domain: initialPageData('domain'),
            formplayer_url: initialPageData('formplayer_url'),
            singleAppMode: true,
            phoneMode: true,
            oneQuestionPerScreen: !initialPageData('is_dimagi'),
            allowedHost: initialPageData('allowed_host'),
            environment: initialPageData('environment'),
            debuggerEnabled: initialPageData('debugger_enabled'),
        });

        hqImport("cloudcare/js/util").injectDialerContext(initialPageData)

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
