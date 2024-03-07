'use strict';
hqDefine("cloudcare/js/formplayer/main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/sentry',
], function (
    $,
    initialPageData,
    FormplayerFrontEnd,
    sentry
) {
    $(function () {
        sentry.initSentry();

        window.MAPBOX_ACCESS_TOKEN = initialPageData.get('mapbox_access_token'); // maps api is loaded on-demand
        var options = {
            apps: initialPageData.get('apps'),
            language: initialPageData.get('language'),
            username: initialPageData.get('username'),
            domain: initialPageData.get('domain'),
            formplayer_url: initialPageData.get('formplayer_url'),
            gridPolyfillPath: initialPageData.get('grid_polyfill_path'),
            debuggerEnabled: initialPageData.get('debugger_enabled'),
            singleAppMode: initialPageData.get('single_app_mode'),
            environment: initialPageData.get('environment'),
        };
        FormplayerFrontEnd.start(options);

        var $menuToggle = $('#commcare-menu-toggle'),
            $navbar = $('#hq-navigation'),
            $trialBanner = $('#cta-trial-banner');
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
        if (initialPageData.get("domain_is_on_trial")) {
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
