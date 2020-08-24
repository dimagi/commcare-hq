/* globals FormplayerFrontend */
hqDefine("cloudcare/js/formplayer/main", [
    "hqwebapp/js/initial_page_data",
],
function (initial_page_data) {
    $(function () {
        // window.MAPBOX_ACCESS_TOKEN = initialPageData('mapbox_access_token'); // maps api is loaded on-demand
        var MAPBOX_ACCESS_TOKEN = initial_page_data.get("mapbox_access_token");
        console.log('main.js file MAPBOX_ACCESS_TOKEN',MAPBOX_ACCESS_TOKEN);
        // var initialPageData = hqImport("hqwebapp/js/initial_page_data").get;
        
        var options = {
            apps: initial_page_data.get('apps'),
            language: initial_page_data.get('language'),
            username: initial_page_data.get('username'),
            domain: initial_page_data.get('domain'),
            formplayer_url: initial_page_data.get('formplayer_url'),
            gridPolyfillPath: initial_page_data.get('grid_polyfill_path'),
            debuggerEnabled: initial_page_data.get('debugger_enabled'),
            singleAppMode: initial_page_data.get('single_app_mode'),
            environment: initial_page_data.get('environment'),
            useLiveQuery: initial_page_data.get('use_live_query'),
        };
        FormplayerFrontend.start(options);

        hqImport("cloudcare/js/util").injectMarkdownAnchorTransforms();

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
        if (initial_page_data.get("domain_is_on_trial")) {
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
