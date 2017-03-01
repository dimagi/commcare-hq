hqDefine("hqwebapp/js/rollout_modal.js", function() {
    $(function() {
        var $modal = $(".rollout-modal"),
            slug = $modal.data("slug"),
            cookie_name = "snooze_" + slug;
        if (!$.cookie(cookie_name)) {
            $modal.modal({
                backdrop: 'static',
                keyboard: false,
                show: true,
            });
            $modal.on('click', '.flag-enable', function() {
                $.get({
                    url: '',    // TODO
                    data: {
                        // TODO
                    },
                    success: function() {
                        window.location.reload(true);
                    },
                    error: function() {
                        alert_user(gettext('We could not turn on the new feature. You will have the opportunity' +
                                           'to turn it on the next time you visit this page.'), 'warning');
                    },
                });
            });
            $modal.on('click', '.flag-snooze', function() {
                $.cookie(cookie_name, true, { expires: 3, path: '/' });
                $modal.modal('hide');
            });
        }
    });
});
