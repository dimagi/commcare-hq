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

    var initPublishStatus = function () {
        var currentAppVersionUrl = initialPageData.reverse('current_app_version');
        var _checkPublishStatus = function () {
            $.ajax({
                url: currentAppVersionUrl,
                success: function (data) {
                    setPublishStatus((!data.latestBuild && data.currentVersion > 1) || (data.latestBuild !== null && data.latestBuild < data.currentVersion));
                },
            });
        };
        _checkPublishStatus();
        // check publish status every 20 seconds
        setInterval(_checkPublishStatus, 20000);

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
