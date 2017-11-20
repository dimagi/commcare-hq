hqDefine("groups/js/all_groups", function() {
    $(function () {
        var $createGroupForm = $("#create_group_form");
        $("button:submit", $createGroupForm).click(function(){
            hqImport('analytics/js/google').track.event("Groups", "Create Group", "", "", {}, function () {
                $createGroupForm.submit();
            });
            return false;
        });
    });
});
