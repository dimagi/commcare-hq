/*
    To use, include this file on a page that also includes hqwebapp/downgrade_modal.html
*/
import noopMetrics from "analytix/js/noopMetrics";
import initialPageData from "hqwebapp/js/initial_page_data";
import $ from "jquery";
import "jquery.cookie/jquery.cookie";

function snooze(slug, domain) {
    $.cookie(cookieName(slug, domain), true, { expires: 1, path: '/', secure: initialPageData.get('secure_cookies') });
}

function cookieName(slug, domain) {
    return "snooze_" + slug + "_" + domain;
}

$(function () {
    var $modal = $("#downgrade-modal"),
        slug = $modal.data("slug"),
        domain = $modal.data("domain");

    if ($modal.length && ! $.cookie(cookieName(slug, domain))) {
        // Show modal on page load
        $modal.modal({
            backdrop: 'static',
            keyboard: false,
            show: true,
        });
    }

    // User clicks to snooze
    $modal.on('click', '#overdue-invoice-snooze', function () {
        $modal.modal('hide');
        snooze(slug, domain);
    });
});

$(function () {
    $("#overdue-invoice-link").on('click', function () {
        noopMetrics.track.event('[Overdue Notification] Clicked Pay invoice now');
    });
    $("#overdue-invoice-snooze").on('click', function () {
        noopMetrics.track.event('[Overdue Notification] Clicked Remind me later');
    });
});
