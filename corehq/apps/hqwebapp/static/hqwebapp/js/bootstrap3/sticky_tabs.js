/*
 * Adds URL hash behavior to bootstrap tabs. This enables bookmarking/refreshing and browser back/forward.
 * Lightly modified from https://stackoverflow.com/questions/18999501/bootstrap-3-keep-selected-tab-on-page-refresh
 */
hqDefine("hqwebapp/js/bootstrap3/sticky_tabs", [
    "jquery",
    "bootstrap",    // needed for $.tab
], function (
    $
) {
    var getHash = function () {
        if (window.location.hash) {
            // .replace handles the #history?form_id=foo style of URL hashes used by
            // the case data page's history tab (case_data.js)
            return window.location.hash.replace(/\?.*/, "");
        }
        return "";
    };

    $(function () {
        var tabSelector = "a[data-toggle='tab']",
            navSelector = ".nav.sticky-tabs",
            hash = getHash(),
            $tabFromUrl = hash ? $("a[href='" + hash + "']") : undefined;

        if ($tabFromUrl && $tabFromUrl.length) {
            $tabFromUrl.tab('show');
        } else {
            $(navSelector + ' ' + tabSelector).first().tab('show');
        }

        $('body').on('click', tabSelector, function (e) {
            var $link = $(this);
            if (!$link.closest(navSelector).length) {
                return true;
            }
            e.preventDefault();
            var tabName = $link.attr('href');
            if (window.history.pushState) {
                window.history.pushState(null, null, tabName);
            } else {
                window.location.hash = tabName;
            }

            $link.tab('show');
            return false;
        });

        $(window).on('popstate', function () {
            var anchor = getHash() || $(navSelector + ' ' + tabSelector).first().attr('href');
            $("a[href='" + anchor + "']").tab('show');
        });
    });
});
