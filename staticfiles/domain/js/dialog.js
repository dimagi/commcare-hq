$(function(){
    $(".delete_link").addClass("dialog_opener");
    $(".delete_dialog").addClass("dialog");
    $(".dialog_opener").each(function (){
        this._dialog = $(this).next('.dialog');
    });
    $(".dialog").dialog({autoOpen: false, modal: true, width: 600});
    $(".dialog_opener").click(function(e){ 
        e.preventDefault();
        this._dialog.dialog('open');
    });
});