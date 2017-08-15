hqDefine("reminders/js/reminders", function() {
    $(function (){
        var unsaved = false;
        $(":input[type='submit'].btn-primary").click(function (){
            unsaved = false;
        });
        $(":input").not(":input[type='submit']").change(function(){ 
            unsaved = true;
        });
        function unloadPage(){ 
            if (unsaved){
                return gettext('You have unsaved changes.');
            }
        }
        window.onbeforeunload = unloadPage;
    });
});
