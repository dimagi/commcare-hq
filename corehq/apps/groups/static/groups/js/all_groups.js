hqDefine("groups/js/all_groups", function() {
    $(function () {
        var $createGroupForm = $("#create_group_form");
        $("button:submit", $createGroupForm).click(function(){
            ga_track_event("Groups", "Create Group", {
                'hitCallback': function () {
                    $createGroupForm.submit();
                },
            });
            return false;
        });
    });
});
