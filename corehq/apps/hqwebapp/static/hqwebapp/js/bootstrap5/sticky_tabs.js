/*
 * Adds URL hash behavior to bootstrap tabs. This enables bookmarking/refreshing and browser back/forward.
 * Lightly modified from https://stackoverflow.com/questions/18999501/bootstrap-3-keep-selected-tab-on-page-refresh
 */
hqDefine("hqwebapp/js/bootstrap5/sticky_tabs", [
    "jquery",
    "es6!hqwebapp/js/bootstrap5_loader",    // needed for $.tab
], function (
    $, bootstrap
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
        var tabSelector = "a[data-bs-toggle='tab']",
            navSelector = ".nav.sticky-tabs",
            hash = getHash(),
            $tabFromUrl = hash ? $("a[href='" + hash + "']") : undefined,
            $altTabSelector = $(navSelector + ' ' + tabSelector).first(),
            tabController;

        // make sure we don't treat all anchor tags as a sticky tab
        if ($tabFromUrl && $tabFromUrl.parents('.sticky-tabs').length === 0) return;

        if ($tabFromUrl && $tabFromUrl.length) {
            tabController = new bootstrap.Tab($tabFromUrl);
            tabController.show();
        } else if ($altTabSelector.length) {
            tabController = new bootstrap.Tab($altTabSelector);
            tabController.show();
        }

        $('body').on('click', tabSelector, function (e) {
            var $link = $(this),
                linkTab = new bootstrap.Tab($link);
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

            linkTab.show();
            return false;
        });

        $(window).on('popstate', function () {
            var anchor = getHash() || $(navSelector + ' ' + tabSelector).first().attr('href'),
                $anchorSelector = $("a[href='" + anchor + "']"),
                anchorTab;
            if ($anchorSelector.length) {
                anchorTab = new bootstrap.Tab($anchorSelector);
                anchorTab.show();
            }
        });
    });
});
