/*globals COMMCAREHQ */
(function () {
    'use strict';
    COMMCAREHQ.app_manager = eventize({});

    COMMCAREHQ.app_manager.setCommcareVersion = function (version) {
        COMMCAREHQ.app_manager.commcareVersion = version;
        COMMCAREHQ.app_manager.fire('change:commcareVersion', {commcareVersion: version});
    };
    COMMCAREHQ.app_manager.checkCommcareVersion = function (version) {
        function versionGE(commcareVersion1, commcareVersion2) {
            function parse(version) {
                version = version.split('.');
                version = [parseInt(version[0]), parseInt(version[1])];
                return version;
            }
            commcareVersion1 = parse(commcareVersion1);
            commcareVersion2 = parse(commcareVersion2);
            if (commcareVersion1[0] > commcareVersion2[0]) {
                return true;
            } else if (commcareVersion1[0] === commcareVersion2[0]) {
                return commcareVersion1[1] >= commcareVersion2[1];

            } else {
                return false;
            }
        }
        return versionGE(COMMCAREHQ.app_manager.commcareVersion, version);
    };
    COMMCAREHQ.app_manager.init = function (args) {
        var lastAppVersion = args.lastAppVersion,
            appVersion = args.appVersion,
            edit = args.edit;

        function updateDOM(update) {
            if (update.hasOwnProperty('app-version')) {
                appVersion = update['app-version'];
                $('.variable-version').text(appVersion);
            }
            if (update.hasOwnProperty('commcare-version')) {
                COMMCAREHQ.app_manager.setCommcareVersion(update['commcare-version']);
            }
            COMMCAREHQ.updateDOM(update);
        }
        COMMCAREHQ.app_manager.updateDOM = updateDOM;
        function getVar(name) {
            var r = $('input[name="' + name + '"]').first().val();
            return JSON.parse(r);
        }
        function resetIndexes($sortable) {
            var indexes = $sortable.find('> * > .index').get(),
                i;
            for (i in indexes) {
                if (indexes.hasOwnProperty(i)) {
                    $(indexes[i]).text(i).trigger('change');
                }
            }
        }
        COMMCAREHQ.resetIndexes = resetIndexes;

        if (edit) {
            (function () {
                var $forms = $('.save-button-form');
                $forms.each(function () {
                    var $form = $(this),
	                    $buttonHolder = $form.find('.save-button-holder');
	                COMMCAREHQ.SaveButton.initForm($form, {
	                    unsavedMessage: "You have unchanged settings",
	                    success: function (data) {
	                        var key;
	                        COMMCAREHQ.app_manager.updateDOM(data.update);
	                        for (key in data.corrections) {
	                            if (data.corrections.hasOwnProperty(key)) {
	                                $form.find('[name="' + key + '"]').val(data.corrections[key]);
	                                $(document).trigger('correction', [key, data.corrections[key]]);
	                            }
	                        }
                            if (data.hasOwnProperty('case_list-show')){
                                var $case_details_screen = $('#detail-screen-config');
                                if (data['case_list-show']) $case_details_screen.show(500);
                                else $case_details_screen.hide(500);
                            }
	                    }
	                }).ui.appendTo($buttonHolder);
                });
            }());
        }

        $('.sidebar').addClass('ui-corner-bl');
        $('#form-tabs').show();
        $('#forms').tab('show');
//        $("#form-tabs").tabs({
//            cookie: {},
//            select: function (event, ui) {
//                if (ui.index === 1 && getVar('edit_mode')) {
//                    // make sure the Make New Build button is set correctly
//                    resetMakeNewBuild();
//                }
//            }
//        }).removeClass('ui-corner-all').removeClass('ui-widget-content').show();
//        $("#form-tabs > ul").removeClass('ui-corner-all').removeClass('ui-widget-content');


        $(".warning").before($('<div />').addClass('ui-icon ui-icon-alert').css('float', 'left'));

        $('.sortable .sort-action').addClass('sort-disabled');
        $('.sortable').each(function () {
            if ($(this).children().not('.sort-disabled').size() < 2) {
                var $sortable = $(this);
                $('.drag_handle', this).each(function () {
                    if ($(this).closest('.sortable')[0] === $sortable[0]) {
                        $(this).removeClass('drag_handle').css({cursor: "auto"}).find('.ui-icon').css({backgroundImage: "none"});
                    }
                });
            }
        });
        $('.sortable').each(function () {
            var $sortable = $(this);
            if ($(this).children().not('.sort-disabled').size() > 1) {
                $(this).sortable({
                    handle: '.drag_handle ',
                    items: ">*:not(.sort-disabled)",
                    update: function (e, ui) {
                        var to = -1,
                            from = -1,
                            $form;
                        $(this).find('> * > .index').each(function (i) {
                            if (from !== -1) {
                                if (from === parseInt($(this).text(), 10)) {
                                    to = i;
                                    return false;
                                }
                            }
                            if (i !== parseInt($(this).text(), 10)) {
                                if (i + 1 === parseInt($(this).text(), 10)) {
                                    from = i;
                                } else {
                                    to = i;
                                    from = parseInt($(this).text(), 10);
                                    return false;
                                }
                            }
                        });
                        if (to !== from) {
                            $form = $(this).find('> .sort-action form');
                            $form.find('[name="from"], [name="to"]').remove();
                            $form.append('<input type="hidden" name="from" value="' + from.toString() + '" />');
                            $form.append('<input type="hidden" name="to"   value="' + to.toString()   + '" />');

                            // disable sortable
                            $sortable.find('.drag_handle .ui-icon').hide('slow');
    //                        $sortable.find('.drag_handle .ui-icon').removeClass('ui-icon').addClass('disabled-ui-icon');
                            $sortable.sortable('option', 'disabled', true);
                            if ($form.find('input[name="ajax"]').first().val() === "true") {
                                resetIndexes($sortable);
                                $.post($form.attr('action'), $form.serialize(), function (data) {
                                    COMMCAREHQ.app_manager.updateDOM(JSON.parse(data).update);
                                    // re-enable sortable
                                    $sortable.sortable('option', 'disabled', false);
                                    $sortable.find('.drag_handle .ui-icon').show(1000);
    //                                $sortable.find('.drag_handle .disabled-ui-icon').removeClass('disabled-ui-icon').addClass('ui-icon');
                                });
                            } else {
                                $form.submit();
                            }
                        }
                    }
                });
            }
        });
        $('.index, .sort-action').hide();

        $('select.applications').change(function () {
            var url = $(this).find('option:selected').attr('value');
            $(document).attr('location', url);
        });
        $('#langs select').change(function () {
            var url = $(this).find('option:selected').attr('value');
            $(document).attr('location', url);
        });

        $("#ic_file").button();
        $("#error").dialog();

        $("#new_app").addClass("dialog_opener");
        $("#new_app_dialog").addClass("dialog");
        $("#new_module").addClass("dialog_opener");
        $("#new_module_dialog").addClass("dialog");





        $(".dialog_opener").each(function () {
            this.my_dialog = $(this).next('.dialog').get();
            this.my_dialog.my_opener = this;
        });
        $(".dialog").dialog({autoOpen: false, modal: true});
        $(".dialog_opener").click(function (e) {
            e.preventDefault();
            $(this.my_dialog).dialog('open');
        });

        // Module Config Edit

        function makeUneditable(row) {
            $(row).removeClass('selected');
            $(row).find('.immutable').show().prev().hide().autocomplete('close');
        }
        $('tr.editable').click(function (e) {
            if (!$(this).hasClass('selected')) {
                var $row = $(this).closest('tr'),
                    $table;
                $row.focus();
                $table = $(this).closest('table');
                $('tr.editable').each(function () {
                    makeUneditable(this);
                });
                $row.addClass('selected');
                $row.find('.immutable').hide().prev().show().trigger('change');
            }
            return false;
        });
        $('html').click(function (e) {
            makeUneditable($('tr.editable'));
        });

        // Auto set input and select values according to the following 'div.immutable'
        $('select').each(function () {
            var val = $(this).next('div.immutable').text();
            if (val) {
                $(this).find('option').removeAttr('selected');
                $(this).find('option[value="' + val + '"]').attr('selected', 'selected');
            }
        });
        $('input[type="text"]').each(function () {
            var val = $(this).next('div.immutable').text();
            if (val) {
                $(this).attr('value', val);
            }
        });

        // autosave forms have one input only, and when that input loses focus,
        // the form is automatically sent AJAX style

        $(".autosave").closest('form').append($("<span />"));
        $(".autosave").closest('.form').append("<td />");
        $(".autosave").closest_form().each(function () {
            $(this).submit(function () {
                var $form = $(this);
                $form.children().last().text('saving...');
                if ($form.find('[name="ajax"]').val() === "false") {
                    return true;
                } else {
                    $.ajax({
                        type: 'POST',
                        url: $form.attr('action') || $form.attr('data-action'),
                        data: $form.my_serialize(),
                        success: function (data) {
                            COMMCAREHQ.app_manager.updateDOM(data.update);
                            $form.children().last().text('saved').delay(1000).fadeOut('slow', function () {$(this).text('').show(); });
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
        $(".autosave").live('change', function () {
            $(this).closest_form().submit();
        });


    //    $('.index').change(function () {
    //        // really annoying hack: the delete dialog is stored at bottom of page so is not found by the above
    //        var uuid = $(this).closest('tr').find('.delete_link').attr('data-uuid');
    //        $('.delete_dialog[data-uuid="' + uuid + '"]').find('[name="index"]').val($(this).text());
    //    });

        $('.index').change(function () {
            // make sure that column_id changes when index changes (after drag-drop)
            $(this).closest('tr').find('[name="index"]').val($(this).text());
        }).trigger('change');

        COMMCAREHQ.app_manager.on('change:commcareVersion', function () {
            $('.commcare-feature').each(function () {
                var version = '' + $(this).data('since-version') || '1.1',
                    upgradeMessage = $('<div class="upgrade-message"/>'),
                    area = $(this);

                if (COMMCAREHQ.app_manager.checkCommcareVersion(version)) {
                    area.find('upgrade-message').remove();
                    area.find('*:not(".hidden")').show();
                } else {
                    area.find('*').hide();
                    upgradeMessage.append(
                        $('<span/>').addClass('ui-icon ui-icon-arrowthick-1-w')
                    ).append(
                        $('<span/>').text('Requires CommCare ' + version)
                    ).appendTo(area);
                }
            });
        });
        COMMCAREHQ.app_manager.setCommcareVersion(args.commcareVersion);
    };
}());