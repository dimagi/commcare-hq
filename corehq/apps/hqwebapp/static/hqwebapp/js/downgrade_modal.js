/*
    To use, include this file on a page that also includes hqwebapp/downgrade_modal.html
*/
hqDefine("hqwebapp/js/downgrade_modal", [
    'analytix/js/kissmetrix',
    'jquery',
    'jquery.cookie/jquery.cookie'
], function (
    kissmetrics,
    $
) {
    function snooze(slug, domain) {
        $.cookie(cookieName(slug, domain), true, { expires: 1, path: '/' });
    }

    // TODO - add domain
    function cookieName(slug, domain) {
        return "snooze_" + slug + "_" + domain;
    }

    $(function () {
        var $modal = $("#downgrade-modal"),
            slug = $modal.data("slug"),
            domain = $modal.data("domain");

        console.log(slug);
        if ($modal.length && ! $.cookie(cookieName(slug, domain))) {
            // Show modal on page load
            $modal.modal({
                backdrop: 'static',
                keyboard: false,
                show: true,
            });
        }

        // User clicks to snooze
        $modal.on('click', '.flag-snooze', function () {
            $modal.modal('hide');
            snooze(slug, domain);
        });
    });

    $(function () {
        $("#overdue-invoice-link").on('click', function () {
            kissmetrics.track.event('[Overdue Banner] Clicked link');
        });
    });
});
