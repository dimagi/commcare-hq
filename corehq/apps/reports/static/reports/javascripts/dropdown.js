$(function(){
    $("#report_select").val(location.pathname);
    $("#report_select").change(function(){
        location.href = $(this).val();
    });
    $("#report_dropdown").dropdown();
    $("#title-bar").addClass('ui-corner-top');
});