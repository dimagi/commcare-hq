import "commcarehq";
import $ from "jquery";
import googleAnalytics from "analytix/js/google";
import { Popover } from "bootstrap5";
import "hqwebapp/js/bootstrap5/main";  // post-link

$(function () {
    var $createGroupForm = $("#create_group_form");
    $("button:submit", $createGroupForm).click(function () {
        googleAnalytics.track.event("Groups", "Create Group", "", "", {}, function () {
            $createGroupForm.submit();
        });
        return false;
    });

    $('.js-case-sharing-alert').each(function (i, el) {
        new Popover(el);
    });
});
