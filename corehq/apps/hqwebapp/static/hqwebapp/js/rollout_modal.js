/* globals alert_user */
/*
    To use, include this file on a page that also includes hqwebapp/rollout_modal.html
*/
hqDefine("hqwebapp/js/rollout_modal.js", function() {
    $(function() {
        var $modal = $(".rollout-modal"),
            slug = $modal.data("slug"),
            cookie_name = "snooze_" + slug;
        if ($modal.length && !$.cookie(cookie_name)) {
            $modal.modal({
                backdrop: 'static',
                keyboard: false,
                show: true,
            });
            $modal.on('click', '.flag-enable', function() {
                $.post({
                    url: hqImport("hqwebapp/js/urllib.js").reverse("enable_vellum_beta"),
                    success: function() {
                        window.location.reload(true);
                    },
                    error: function() {
                        $modal.modal('hide');
                        alert_user(gettext('We could not turn on the new feature. You will have the opportunity ' +
                                           'to turn it on the next time you visit this page.'), 'danger');
                    },
                });
                window.analytics.usage("Soft Rollout", "enable", slug);
            });
            $modal.on('click', '.flag-snooze', function() {
                $.cookie(cookie_name, true, { expires: 3, path: '/' });
                $modal.modal('hide');
                window.analytics.usage("Soft Rollout", "snooze", slug);
            });
        }
    });
});
