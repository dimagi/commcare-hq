/* globals FormplayerFrontend */
hqDefine("cloudcare/js/formplayer/main", function() {
    $(function() {
        var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        window.GMAPS_API_KEY = initialPageData('maps_api_key'); // maps api is loaded on-demand
        var options = {
            apps: initialPageData('apps'),
            language: initialPageData('language'),
            username: initialPageData('username'),
            domain: initialPageData('domain'),
            formplayer_url: initialPageData('formplayer_url'),
            gridPolyfillPath: initialPageData('grid_polyfill_path'),
            debuggerEnabled: initialPageData('debugger_enabled'),
            singleAppMode: initialPageData('single_app_mode'),
            environment: initialPageData('environment'),
            useLiveQuery: initialPageData('use_live_query'),
        };
        FormplayerFrontend.start(options);

        // todo cookies to save state
        var $menuToggle = $('#commcare-menu-toggle'),
            $navbar = $('#hq-navigation');
        // if cookie exists:
        $menuToggle.data('minimized', 'yes');
        $navbar.css('margin-top', '-' + $navbar.outerHeight() + 'px');
        $menuToggle.click(function (e) {
            if ($menuToggle.data('minimized') === 'yes') {
                $menuToggle.data('minimized', 'no');
                $navbar.css('margin-top', '');
                $menuToggle.text(gettext('Hide Full Menu'));
            } else {
                $menuToggle.data('minimized', 'yes');
                $navbar.css('margin-top', '-' + $navbar.outerHeight() + 'px');
                $menuToggle.text(gettext('Show Full Menu'));
            }
            e.preventDefault();
        });

        $(window).on('resize', function () {
            if ($menuToggle.data('minimized') === 'yes') {
                $navbar.css('margin-top', '-' + $navbar.outerHeight() + 'px');
            }
        });
    });
});
