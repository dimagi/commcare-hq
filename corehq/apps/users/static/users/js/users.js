$(function(){

    $('#user-options li').each(function(){
        var url = $(this).find('a').attr('href');
        if (location.pathname.indexOf(url) == 0) {
            $(this).addClass('selected'); 
        }
    });

    // for striped tables
    $('tr.same_as_last').each(function(){
        $(this).addClass(
            $(this).prev().hasClass('odd') ? "odd" : "even"
        );

    });

    (function makeStatusMessageFade(){
        $("#status_msg").css({height: $("#main_container").height(), width: $("#main_container").width()});
        $("#status_msg").delay(900).fadeOut('slow');
    })();

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

    $(".add_link").addClass("dialog_opener");
    $(".add_dialog").addClass("dialog");



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
