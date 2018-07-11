/*
 * Adds URL hash behavior to bootstrap tabs. This enables bookmarking/refreshing and browser back/forward.
 * Lightly modified from https://stackoverflow.com/questions/18999501/bootstrap-3-keep-selected-tab-on-page-refresh
 */
hqDefine("hqwebapp/js/tab_url_hashes", [
    "jquery",
], function(
    $
) {
    $(function(){
        var tabSelector = "a[data-toggle='tab']",
            navSelector = ".nav.sticky-tabs";
        if (window.location.hash) {
            $("a[href='" + window.location.hash + "']").tab('show');
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
            var anchor = window.location.hash || $(navSelector + ' ' + tabSelector).first().attr('href');
            $("a[href='" + anchor + "']").tab('show');
        });
    });
});
