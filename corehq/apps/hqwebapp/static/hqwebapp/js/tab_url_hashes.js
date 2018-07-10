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
        if (window.location.hash) {
            $("a[href='" + window.location.hash + "']").tab('show');
        } else {
            $("a[data-toggle='tab']:first").tab('show');
        }

        $('body').on('click', "a[data-toggle='tab']", function (e) {
            e.preventDefault();
            var tabName = this.getAttribute('href')
            if (window.history.pushState) {
                window.history.pushState(null, null, tabName);
            } else {
                window.location.hash = tabName;
            }

            $(this).tab('show');
            return false;
        });

        $(window).on('popstate', function () {
            var anchor = window.location.hash || $("a[data-toggle='tab']").first().attr('href');
            $("a[href='" + anchor + "']").tab('show');
        });
    });
});
