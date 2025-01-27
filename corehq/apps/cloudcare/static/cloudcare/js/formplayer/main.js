hqDefine("cloudcare/js/formplayer/main", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'cloudcare/js/formplayer/app',
    'cloudcare/js/sentry',
    'commcarehq',
], function (
    $,
    initialPageData,
    FormplayerFrontEnd,
    sentry,
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
            debuggerEnabled: initialPageData.get('debugger_enabled'),
            singleAppMode: false,
            environment: initialPageData.get('environment'),
        };
        FormplayerFrontEnd.getXSRF(options).then(() =>
            FormplayerFrontEnd.start(options),
        );

        var $menuToggle = $('#commcare-menu-toggle'),
            $navbar = $('#hq-navigation'),
            $trialBanner = $('#cta-trial-banner');
        var hideMainMenu = function () {
            $menuToggle.data('minimized', 'yes');
            $navbar.addClass("d-none");
            $trialBanner.addClass("d-none");
            $menuToggle.text(gettext('Show Full Menu'));
        };
        var showMainMenu = function () {
            $menuToggle.data('minimized', 'no');
            $navbar.removeClass("d-none");
            $trialBanner.removeClass("d-none");
            $navbar.css('margin-top', '');
            $menuToggle.text(gettext('Hide Full Menu'));
        };

        // Show the top HQ nav for new users, so they know how to get back to HQ,
        // but hide it for more mature users so it's out of the way
        if (initialPageData.get("domain_is_on_trial")) {
            showMainMenu();
        } else {
            hideMainMenu();
        }
        $menuToggle.click(function (e) {
            if ($menuToggle.data('minimized') === 'yes') {
                showMainMenu();
            } else {
                hideMainMenu();
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
