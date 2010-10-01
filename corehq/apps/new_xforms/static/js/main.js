$(function(){
    $("#form-tabs").tabs({
    }).removeClass('ui-corner-all').addClass('ui-corner-bottom');

    $("#applications").addClass('ui-widget ui-widget-content ui-corner-top');
    $("#modules").addClass('ui-widget ui-widget-content ui-corner-bl');
    $("#modules h2").addClass('ui-corner-all');
    $("#modules ul li").addClass('ui-corner-all');
    $("#modules ul li div").addClass('ui-corner-top');
    $("#modules ul").addClass('ui-corner-bottom');
    //$("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    $("#form-tabs > ul").removeClass('ui-corner-all');
    $("#forms").removeClass('ui-corners-all').addClass('ui-corner-bottom');
    $("#empty").addClass('ui-widget ui-widget-content ui-corner-bottom');
    $(".message").addClass('ui-state-highlight ui-corner-all');
    $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));
    $('.sortable').sortable({
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
            //alert(to + " " + from)
            $form = $(this).find('> .sort-action form');
            $form.append('<input type="hidden" name="from" value="' + from + '"');
            $form.append('<input type="hidden" name="to"   value="' + to   + '"');
            $form.submit();
        },
        items: ">*:not(.sort-disabled)",
    }).disableSelection();
    $('.index, .sort-action').hide();

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
    $('tr.editable').click(function(e){
        //e.preventDefault();
        if($(this).hasClass('selected')) {return;}
        var $row = $(this).closest('tr');
        var $table = $(this).closest('table');
        $('tr.editable').each(function(){
            $(this).removeClass('selected');
            $(this).find('.immutable').show().prev().hide();
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
                var $input = $(this).clone();
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

        $(this).find('option').removeAttr('selected');
        $(this).find('option[value="' + val + '"]').attr('selected', 'selected');

    });
    $('input[type="text"]').each(function(){
        var val = $(this).next('div.immutable').text();

        $(this).attr('value', val);
    })


});