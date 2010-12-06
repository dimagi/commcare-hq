$.prototype.iconify = function(icon) {
    $icon = $("<div/>").addClass('ui-icon ' + icon).css('float', 'left');
    $(this).prepend($icon);
};

$(function(){
    $('.hidden').hide();
    $('.delete_link').iconify('ui-icon-closethick');
    $('.new_link').iconify('ui-icon-plusthick');
    $('.edit_link').iconify('ui-icon-pencil');


    $("#form-tabs").tabs({
        cookie: {}
    }).removeClass('ui-corner-all').addClass('ui-corner-bottom');

    $("#title-bar").addClass('container ui-corner-top');
    $("#main-content").addClass('container ui-corner-bottom');
    $("#modules").addClass('ui-widget ui-widget-content ui-corner-bl');
    $("#modules h2").addClass('ui-corner-all');
    $("#modules ul li").addClass('ui-corner-all');
    $("#modules ul li div").addClass('ui-corner-top');
    $("#modules ul").addClass('ui-corner-bottom');
    //$("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    $("#form-tabs > ul").removeClass('ui-corner-all');
    $("#forms").removeClass('ui-corners-all').addClass('ui-corner-bottom');
    $("#empty").addClass('ui-widget ui-widget-content ui-corner-bottom');
    $('.config').wrap('<div />').parent().addClass('container ui-corner-all');
    $(".message").addClass('ui-state-highlight ui-corner-all');
    $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));
    $('.container').addClass('ui-widget ui-widget-content');

    $('.sortable .sort-action').addClass('sort-disabled');
    $('.sortable').each(function(){
        if($(this).children().not('.sort-disabled').size() > 1) {
            $(this).sortable({
                update: function(e, ui){
                    var to = -1;
                    var from = -1;
                    $(this).find('> * > .index').each(function(i){
                        if(to == -1) {
                            if(i != $(this).text()) {
                                to = i;
                                from = $(this).text();
                            }
                        }
                    });
                    if(to != from) {
                        $form = $(this).find('> .sort-action form');
                        $form.append('<input type="hidden" name="from" value="' + from + '" />');
                        $form.append('<input type="hidden" name="to"   value="' + to   + '" />');
                        $form.submit();
                    }
                },
                items: ">*:not(.sort-disabled)"
            });
        }
    });
    $('.index, .sort-action').hide();

    $('select.applications').change(function(){
        var url = $(this).find('option:selected').attr('value');
        $(document).attr('location', url);
    });
    $('#langs select').change(function(){
        var url = $(this).find('option:selected').attr('value');
        $(document).attr('location', url);
    });
    $(".button").button().wrap('<span />');
    $("#ic_file").button();
    $("input[type='submit']").button();
    $("#error").dialog();

    $("#new_app").addClass("dialog_opener");
    $("#new_app_dialog").addClass("dialog");
    $("#new_module").addClass("dialog_opener");
    $("#new_module_dialog").addClass("dialog");

    $(".delete_link").addClass("dialog_opener");
    $(".delete_dialog").addClass("dialog");



    $(".dialog_opener").each(function (){
        this._dialog = $(this).next('.dialog');
    });
    $(".dialog").dialog({autoOpen: false, modal: true});
    $(".dialog_opener").click(function(e){
        e.preventDefault();
       this._dialog.dialog('open');
    });

    // Module Config Edit
    $('select[name="format"]').change(function(){
        var $enum = $(this).parent().next().find('input[name="enum"]');
        if($(this).attr('value') == "enum") {
            $enum.show();
        }
        else {
            $enum.hide();
        }
    });
    $('.editable .immutable').prev().hide();
    //$('table .editable').last().find('.immutable').hide().prev().show();
    $('tr.editable').mouseup(function(e){
        //e.preventDefault();
        if($(this).hasClass('selected')) {return;}
        var $row = $(this).closest('tr');
        $row.focus();
        var $table = $(this).closest('table');
        $('tr.editable').each(function(){
            $(this).removeClass('selected');
            $(this).find('.immutable').show().prev().hide().autocomplete('close');
        });
        $row.addClass('selected');
        $row.find('.immutable').hide().prev().show().trigger('change');
    });
    $('.form a.submit').click(function(e){
        e.preventDefault();
        var $row = $(this).closest('tr');
        var $form = $('<form method="post" action="' + $(this).attr('href') + '" enctype="multipart/form-data"></form>');
        $row.find('[name]').each(function(){
            if($(this).attr('type') == 'file'){
                var $input = $(this);
                $input.hide();
                $form.append($input);
            }
            else {
                var $input = $('<input type="text" />');
                $input.attr('name', $(this).attr('name'));
                $input.attr('value', $(this).attr('value'));
                $input.hide();
                $form.append($input);
            }
        });
        $('body').append($form);
        $form.submit();
    });

    // Auto set input and select values according to the following 'div.immutable'
    $('select').each(function(){
        var val = $(this).next('div.immutable').text();
        if(val) {
            $(this).find('option').removeAttr('selected');
            $(this).find('option[value="' + val + '"]').attr('selected', 'selected');
        }
    });
    $('input[type="text"]').each(function(){
        var val = $(this).next('div.immutable').text();
        if(val) {
            $(this).attr('value', val);
        }
    });

    $("#new_app_message").click(function(){
        $("#new_app_dialog").dialog('open');
    });
});