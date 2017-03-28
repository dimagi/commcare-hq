hqDefine("groups/js/all_groups.js", function() {
    $(function () {
        var $createGroupForm = $("#create_group_form");
        debugger;
        $("button:submit", $createGroupForm).click(function(){
            ga_track_event("Groups", "Create Group", {
               'hitCallback': function () {
                   $createGroupForm.submit();
               }
            });
            return false;
        });
    });
});
