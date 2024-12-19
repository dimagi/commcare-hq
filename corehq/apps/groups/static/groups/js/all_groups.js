"use strict";
hqDefine("groups/js/all_groups", [
    'jquery',
    'analytix/js/google',
    'es6!hqwebapp/js/bootstrap5_loader',
    // Just importing main.py so the post-link function is accessible, function parameter not needed
    'hqwebapp/js/bootstrap5/main',
    'commcarehq',
], function (
    $,
    googleAnalytics,
    bootstrap
) {
    $(function () {
        var $createGroupForm = $("#create_group_form");
        $("button:submit", $createGroupForm).click(function () {
            googleAnalytics.track.event("Groups", "Create Group", "", "", {}, function () {
                $createGroupForm.submit();
            });
            return false;
        });

        $('.js-case-sharing-alert').each(function (i, el) {
            new bootstrap.Popover(el);
        });
    });
});
