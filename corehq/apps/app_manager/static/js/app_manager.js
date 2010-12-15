$.prototype.iconify = function(icon) {
    $icon = $("<div/>").addClass('ui-icon ' + icon).css('float', 'left');
    $(this).css('width', "16px").prepend($icon);
};

function resetIndexes($sortable) {
    var indexes = $sortable.find('> * > .index').get();
    for(var i in indexes) {
        $(indexes[i]).text(i).trigger('change');
    }
}


$(function(){
    $('.hidden').hide();
    $('.delete_link').iconify('ui-icon-closethick');
    $(".delete_link").addClass("dialog_opener");
    $(".delete_dialog").addClass("dialog");
    $('.new_link').iconify('ui-icon-plusthick');
    $('.edit_link').iconify('ui-icon-pencil');
    var dragIcon = 'ui-icon-grip-dotted-horizontal';
    $('.drag_handle').iconify(dragIcon);


    $("#form-tabs").tabs({
        cookie: {}
    }).removeClass('ui-corner-all').removeClass('ui-widget-content');
    $("#form-tabs > ul").removeClass('ui-corner-all').removeClass('ui-widget-content');

    //$("#main-content").addClass('container ui-corner-bottom');
    $("#modules").addClass('ui-widget-content ui-corner-bl');
    $("#modules h2").addClass('ui-corner-all');
    $("#modules ul li").addClass('ui-corner-all');
    $("#modules ul li div").addClass('ui-corner-top');
    $("#modules ul").addClass('ui-corner-bottom');
    //$("#form-view").addClass('ui-widget ui-widget-content ui-corner-br');
    //$("#forms").removeClass('ui-corners-all').addClass('ui-corner-bottom');
    //$("#empty").addClass('ui-widget ui-widget-content ui-corner-bottom');
    $('.config').wrap('<div />').parent().addClass('container block ui-corner-all');
    $(".message").addClass('ui-state-highlight ui-corner-all');
    $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));

    $('.sortable .sort-action').addClass('sort-disabled');
    $('.sortable').each(function(){
        if($(this).children().not('.sort-disabled').size() < 2) {
            $('.drag_handle', this).removeClass('drag_handle').css({cursor: "auto"}).find('.ui-icon').css({backgroundImage: "none"});
        }
    });
    $('.sortable').each(function(){
        var $sortable = $(this);
        if($(this).children().not('.sort-disabled').size() > 1) {
            $(this).sortable({
                handle: '.drag_handle ',
                items: ">*:not(.sort-disabled)",
                update: function(e, ui){
                    var to = -1;
                    var from = -1;
                    $(this).find('> * > .index').each(function(i){
                        if(from != -1) {
                            if(from == $(this).text()) {
                                to = i;
                                return false;
                            }
                        }
                        if(i != $(this).text()) {
                            if(i+1 == $(this).text()) {
                                from = i;
                            }
                            else {
                                to = i;
                                from = $(this).text();
                                return false;
                            }
                        }
                    });
                    if(to != from) {
                        var $form = $(this).find('> .sort-action form');
                        $form.find('[name="from"], [name="to"]').remove();
                        $form.append('<input type="hidden" name="from" value="' + from + '" />');
                        $form.append('<input type="hidden" name="to"   value="' + to   + '" />');

                        // disable sortable
                        $sortable.find('.drag_handle .ui-icon').hide('slow');
                        $sortable.sortable('option', 'disabled', true);
                        if($form.find('input[name="ajax"]').first().val() == "true") {
                            resetIndexes($sortable);
                            $.post($form.attr('action'), $form.serialize(), function(){
                                // re-enable sortable
                                $sortable.sortable('option', 'disabled', false);
                                $sortable.find('.drag_handle .ui-icon').show(1000);
                            });
                        }
                        else {
                            $form.submit();
                        }
                    }
                }
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

    $("#ic_file").button();
    $("#error").dialog();

    $("#new_app").addClass("dialog_opener");
    $("#new_app_dialog").addClass("dialog");
    $("#new_module").addClass("dialog_opener");
    $("#new_module_dialog").addClass("dialog");





    $(".dialog_opener").each(function (){
        this._dialog = $(this).next('.dialog').get();
        this._dialog._opener = this;
    });
    $(".dialog").dialog({autoOpen: false, modal: true});
    $(".dialog_opener").click(function(e){
        e.preventDefault();
       $(this._dialog).dialog('open');
    });

    // Module Config Edit
//    $('select[name="format"]').change(function(){
//        var $enum = $(this).parent().next().find('input[name="enum"]');
//        if($(this).attr('value') == "enum") {
//            $enum.show();
//        }
//        else {
//            $enum.hide();
//        }
//    });
//    $('.editable .immutable').prev().hide();
    //$('table .editable').last().find('.immutable').hide().prev().show();
    function makeUneditable(row) {
        $(row).removeClass('selected');
        $(row).find('.immutable').show().prev().hide().autocomplete('close');
    }
    $('tr.editable').click(function(e){
        if(! $(this).hasClass('selected')) {
            var $row = $(this).closest('tr');
            $row.focus();
            var $table = $(this).closest('table');
            $('tr.editable').each(function(){
                makeUneditable(this);
            });
            $row.addClass('selected');
            $row.find('.immutable').hide().prev().show().trigger('change');
        }
        return false;
    });
    $('html').click(function(e){
        makeUneditable($('tr.editable'));
    });
//    $('.form .form-action').click(function(e){
//        e.preventDefault();
//        var $row = $(this).closest('tr');
//        var href = $(this).text();
//        var $form = $('<form method="post" action="' + href + '" enctype="multipart/form-data"></form>');
//        $row.find('[name]').each(function(){
//            if($(this).attr('type') == 'file'){
//                var $input = $(this);
//                $input.hide();
//                $form.append($input);
//            }
//            else {
//                var $input = $('<input type="text" />');
//                $input.attr('name', $(this).attr('name'));
//                $input.attr('value', $(this).attr('value'));
//                $input.hide();
//                $form.append($input);
//            }
//        });
//        $('body').append($form);
//        $form.submit();
//    });

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

    // autosave forms have one input only, and when that input loses focus,
    // the form is automatically sent AJAX style

    $.fn.closest_form = function(){
        return this.closest('form, .form');
    }
    $.fn.my_serialize = function() {
        var data = this.find('[name]').serialize();
        return data;
    }
    $(".autosave").closest('form').append($("<span />"));
    $(".autosave").closest('.form').append("<td />");
    $(".autosave").closest_form().submit(function(){
        var $form = $(this);
        $form.children().last().text('saving...');
        $.post($form.attr('action') || $form.attr('data-action'), $form.my_serialize(), function(){
            $form.children().last().text('saved').delay(1000).fadeOut('slow', function(){$(this).text('').show()});
        });
        return false;
    });
    $(".autosave").change(function(){
        $(this).closest_form().submit();
    });


    $('.submit').click(function(e){
        e.preventDefault();
        var $form = $(this).closest('.form');
        var data = $form.my_serialize();
        var action = $form.attr('data-action');
        $.postGo(action, $.unparam(data));
    });

    $('.index').change(function(){
        // really annoying hack: the delete dialog is stored at bottom of page so is not found by the above
        var uuid = $(this).closest('tr').find('.delete_link').attr('data-uuid');
        $('.delete_dialog[data-uuid="' + uuid + '"]').find('[name="column_id"]').val($(this).text());
    });
});