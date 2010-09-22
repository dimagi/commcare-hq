$(function(){
    $("#form-tabs").tabs({
    }).removeClass('ui-corner-all').addClass('ui-corner-bottom');

    $("#applications").addClass('ui-widget ui-widget-content ui-corner-top');
    $("#modules").addClass('ui-widget ui-widget-content ui-corner-bl');
    $("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    $("#form-tabs > ul").removeClass('ui-corner-all');
    $("#forms").removeClass('ui-corners-all').addClass('ui-corners-bottom');
    $('#applications select').change(function(){
        var url = $(this).find('option:selected').attr('value');
        $(document).attr('location', url);
    });

    $(".button").button();
    $("#ic_file").button();
    $("input[type='submit']").button();
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
});