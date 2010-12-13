$(function() {
    $(".button").button().wrap('<span />').addClass('shadow');
    $("input[type='submit']").button().addClass('shadow');
    $("input[type='text'], input[type='password']").addClass('shadow').addClass('ui-corner-all');

    $("#title-bar").addClass('container ui-corner-top');
    $('#main_container').addClass('ui-corner-all container shadow');
    $('.container').addClass('ui-widget ui-widget-content');
    
});