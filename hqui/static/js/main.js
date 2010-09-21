$(function(){
    $("#form-tabs").tabs({
    }).removeClass('ui-corner-all').addClass('ui-corner-bottom');

    $("#applications").addClass('ui-widget ui-widget-content ui-corner-top');
    $("#modules").addClass('ui-widget ui-widget-content ui-corner-bl');
    $("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    $("#form-tabs > ul").removeClass('ui-corner-all');
    $("#forms").removeClass('ui-corners-all').addClass('ui-corners-bottom');
    $('#applications select').change(function(){
        $(document).attr('location', $(this).find('option:selected').attr('value'));
    });
});