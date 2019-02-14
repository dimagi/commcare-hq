hqDefine("app_manager/js/menu", [
    'jquery',
    'hqwebapp/js/initial_page_data',
    'hqwebapp/js/layout',
    'app_manager/js/app_manager_utils',
], function (
    $,
    initialPageData,
    layout,
    utils
) {
    var setPublishStatus = function (isOn) {
        if (isOn) {
            layout.showPublishStatus();
        } else {
            layout.hidePublishStatus();
        }
    };

    var initLangs = function () {
        $('#langs select').change(function () {
            var lang = $(this).find('option:selected').attr('value'),
                loc = window.location,
                params = {},
                searchString = "";
            if (loc.search) {
                params = $.unparam(loc.search.slice(1));
            }
            params['lang'] = lang;
            searchString = "?" + $.param(params);
            $(document).attr('location', loc.pathname + searchString + loc.hash);
        });
    };

    // Frequently poll for changes to app, for the sake of showing the "Updates available to publish" banner.
    // Avoid checking if the user is active, which here is defined by the browser tab having focus.
    var initPublishStatus = function () {
        var frequency = 20000,
            isIdle = false,
            lastActivity = (new Date()).getTime(),
            msSinceLastActivity = function () {
                return (new Date()).getTime() - lastActivity;
            },
            updateLastActivity = function () {
                isIdle = false;
                if (msSinceLastActivity() > frequency) {
                    // If they're coming back after long inactivity, do an immediate check
                    _checkPublishStatus(true);
                }
                lastActivity = (new Date()).getTime();
            };


        $(window).focus(updateLastActivity);
        $(window).blur(function () {
            isIdle = true;
        });

        var currentAppVersionUrl = initialPageData.reverse('current_app_version');
        var _checkPublishStatus = function () {
            if (!isIdle) {
                $.ajax({
                    url: currentAppVersionUrl,
                    success: function (data) {
                        setPublishStatus((!data.latestBuild && data.currentVersion > 1) || (data.latestBuild !== null && data.latestBuild < data.currentVersion));
                    },
                });
            }
        };
        _checkPublishStatus();

        setInterval(_checkPublishStatus, frequency);

        // sniff ajax calls to other urls that make app changes
        utils.handleAjaxAppChange(function () {
            setPublishStatus(true);
        });
    };

    $(function () {
        initLangs();
        initPublishStatus();
    });

    return {
        setPublishStatus: setPublishStatus,
    };
});
