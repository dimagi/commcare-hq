hqDefine("groups/js/all_groups", [
    'jquery',
    'analytix/js/google',
    // Just importing main.py so the post-link function is accessible, function parameter not needed
    'hqwebapp/js/main',
], function (
    $,
    googleAnalytics
) {
    $(function () {
        var $createGroupForm = $("#create_group_form");
        $("button:submit", $createGroupForm).click(function () {
            googleAnalytics.track.event("Groups", "Create Group", "", "", {}, function () {
                $createGroupForm.submit();
            });
            return false;
        });
    });
});
