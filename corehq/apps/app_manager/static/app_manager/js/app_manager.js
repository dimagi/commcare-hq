$(function(){
    function getVar(name) {
        var r = $('input[name="' + name + '"]').first().val();
        return JSON.parse(r);
    }
    function resetIndexes($sortable) {
        var indexes = $sortable.find('> * > .index').get();
        for(var i in indexes) {
            $(indexes[i]).text(i).trigger('change');
        }
    }



    function makeBuildErrorLinksSwitchTabs() {
        $("#build-errors a").click(function(){
            $('#form-tabs').tabs("select", 0);
        });
    }
//    (function makeLangsFloat() {
//        var $langsDiv = $("#langs"),
//            top = parseInt($langsDiv.css("top").substring(0,$langsDiv.css("top").indexOf("px"))),
//            offset = $langsDiv.offset().top;
//        $(window).scroll(function () {
//            var newTop = top+$(document).scrollTop()-offset+49;
//            newTop = newTop > 0 ? newTop : 0;
//            $langsDiv.animate({top:newTop + "px"},{duration:100,queue:false});
//        });
//    }());

    $("#form-tabs").tabs({
        cookie: {},
        select: function(event, ui){
            if(ui.index == 1 && getVar('edit_mode')) {
                // reload when Release Manager tab is clicked
                location.href = location.href;
            }
        }
    }).removeClass('ui-corner-all').removeClass('ui-widget-content').show();
    $("#form-tabs > ul").removeClass('ui-corner-all').removeClass('ui-widget-content');


    $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));

    $('.sortable .sort-action').addClass('sort-disabled');
    $('.sortable').each(function(){
        if($(this).children().not('.sort-disabled').size() < 2) {
            var $sortable = $(this);
            $('.drag_handle', this).each(function(){
                if($(this).closest('.sortable')[0] == $sortable[0]) {
                    $(this).removeClass('drag_handle').css({cursor: "auto"}).find('.ui-icon').css({backgroundImage: "none"});
                }
            });
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
//                        $sortable.find('.drag_handle .ui-icon').removeClass('ui-icon').addClass('disabled-ui-icon');
                        $sortable.sortable('option', 'disabled', true);
                        if($form.find('input[name="ajax"]').first().val() == "true") {
                            resetIndexes($sortable);
                            $.post($form.attr('action'), $form.serialize(), function(data){
                                COMMCAREHQ.updateDOM(JSON.parse(data).update);
                                // re-enable sortable
                                $sortable.sortable('option', 'disabled', false);
                                $sortable.find('.drag_handle .ui-icon').show(1000);
//                                $sortable.find('.drag_handle .disabled-ui-icon').removeClass('disabled-ui-icon').addClass('ui-icon');
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

    // autosave forms have one input only, and when that input loses focus,
    // the form is automatically sent AJAX style

    $.fn.closest_form = function(){
        return this.closest('form, .form');
    };
    $.fn.my_serialize = function() {
        var data = this.find('[name]').serialize();
        return data;
    };
    $(".autosave").closest('form').append($("<span />"));
    $(".autosave").closest('.form').append("<td />");
    $(".autosave").closest_form().each(function(){
      //alert($(this).attr('action'));
      $(this).submit(function(){
        var $form = $(this);
        $form.children().last().text('saving...');
        if($form.find('[name="ajax"]').val() == "false") {
            return true;
        }
        else {
//            $.post($form.attr('action') || $form.attr('data-action'), $form.my_serialize(), function(data){
//                updateDOM(JSON.parse(data)['update']);
//
//                $form.children().last().text('saved').delay(1000).fadeOut('slow', function(){$(this).text('').show()});
//            });
            $.ajax({
                type: 'POST',
                url: $form.attr('action') || $form.attr('data-action'),
                data: $form.my_serialize(),
                success: function(data){
                    COMMCAREHQ.updateDOM(data.update);
                    $form.children().last().text('saved').delay(1000).fadeOut('slow', function(){$(this).text('').show()});
                },
                dataType: 'json',
                error: function () {
                    $form.children().last().text('Error occurred');
                }
            });
            return false;
        }
      });
    });
    $(".autosave").live('change', function(){
        $(this).closest_form().submit();
    });


    $('.submit').click(function(e){
        e.preventDefault();
        var $form = $(this).closest('.form, form');
        var data = $form.my_serialize();
        var action = $form.attr('action') || $form.attr('data-action');
        $.postGo(action, $.unparam(data));
    });


    $('.index').change(function(){
        // really annoying hack: the delete dialog is stored at bottom of page so is not found by the above
        var uuid = $(this).closest('tr').find('.delete_link').attr('data-uuid');
        $('.delete_dialog[data-uuid="' + uuid + '"]').find('[name="index"]').val($(this).text());
    });

    $('.index').change(function(){
        // make sure that column_id changes when index changes (after drag-drop)
        $(this).closest('tr').find('[name="index"]').val($(this).text());
    }).trigger('change');
    
    makeBuildErrorLinksSwitchTabs();

    $("#make-new-build").submit(function () {
        var comment = window.prompt("Please write a comment about the build you're making to help you remember later:");
        if (comment || comment === "") {
            $(this).find("input[name='comment']").val(comment);
        } else {
            return false;
        }
    });
});