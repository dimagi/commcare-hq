// some default dialog settings

$(function(){
    $(".delete_link").addClass("dialog_opener");
    $(".dialog_opener").each(function (){
        this._dialog = $(this).next('.dialog');
    });
    $(".dialog").dialog({autoOpen: false, modal: true});
    $(".dialog_opener").click(function(e){
        e.preventDefault();
        this._dialog.dialog('open');
    });
});