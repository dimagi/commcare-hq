$(function(){
    $("#form-tabs").tabs({
    }).removeClass('ui-corner-all').addClass('ui-corner-bottom');

    $("#applications").addClass('ui-widget ui-widget-content ui-corner-top');
    $("#modules").addClass('ui-widget ui-widget-content ui-corner-bl');
    $("#modules ul li").addClass('ui-corner-all');
    $("#modules ul").addClass('ui-corner-all');
    //$("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    $("#form-tabs > ul").removeClass('ui-corner-all');
    $("#forms").removeClass('ui-corners-all').addClass('ui-corner-bottom');
    $("#empty").addClass('ui-widget ui-widget-content ui-corner-bottom');
    $(".message").addClass('ui-state-highlight ui-corner-all');
    $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));

    $('#applications select').change(function(){
        var url = $(this).find('option:selected').attr('value');
        $(document).attr('location', url);
    });

    $(".button").button();
    $("#ic_file").button();
    $("input[type='submit']").button();
    $("#error").dialog();
    $("#new_app_dialog").dialog({autoOpen:false, modal:true});
    $("#new_app").click(function(e){
        e.preventDefault();
        $("#new_app_dialog").dialog('open');
    });
    $("#new_module_dialog").dialog({autoOpen:false, modal:true});
    $("#new_module").click(function(e){
        e.preventDefault();
        $("#new_module_dialog").dialog('open');
    });

    $(".delete_link").each(function (){
        this._dialog = $(this).next('.delete_dialog');
    });
    $(".delete_dialog").dialog({autoOpen: false, modal: true});
    $(".delete_link").click(function(e){
        e.preventDefault();
       this._dialog.dialog('open');
    });
});