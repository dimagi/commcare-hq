/* globals FormplayerFrontend */
hqDefine("cloudcare/js/formplayer/main", function () {
    $(function () {
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

        var $menuToggle = $('#commcare-menu-toggle'),
            $navbar = $('#hq-navigation'),
            $trialBanner = $('#cta-get-demo-banner');
        var hideMenu = function () {
            $menuToggle.data('minimized', 'yes');
            $navbar.hide();
            $trialBanner.hide();
            $menuToggle.text(gettext('Show Full Menu'));
        };
        var showMenu = function () {
            $menuToggle.data('minimized', 'no');
            $navbar.show();
            $trialBanner.show();
            $navbar.css('margin-top', '');
            $menuToggle.text(gettext('Hide Full Menu'));
        };

        // Show the top HQ nav for new users, so they know how to get back to HQ,
        // but hide it for more mature users so it's out of the way
        if (initialPageData("domain_is_on_trial")) {
            showMenu();
        } else {
            hideMenu();
        }
        $menuToggle.click(function (e) {
            if ($menuToggle.data('minimized') === 'yes') {
                showMenu();
            } else {
                hideMenu();
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
