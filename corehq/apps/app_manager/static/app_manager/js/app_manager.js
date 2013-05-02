/*globals COMMCAREHQ */
(function () {
    'use strict';
    COMMCAREHQ.app_manager = eventize({});

    COMMCAREHQ.app_manager.setCommcareVersion = function (version) {
        COMMCAREHQ.app_manager.commcareVersion(version);
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
        return versionGE(COMMCAREHQ.app_manager.commcareVersion(), version);
    };
    COMMCAREHQ.app_manager.init = function (args) {
        var appVersion = args.appVersion,
            edit = args.edit;
        COMMCAREHQ.app_manager.commcareVersion = ko.observable();

        function updateDOM(update) {
            if (update.hasOwnProperty('app-version')) {
                appVersion = update['app-version'];
                $('.variable-version').text(appVersion);
            }
            if (update.hasOwnProperty('commcare-version')) {
                COMMCAREHQ.app_manager.setCommcareVersion(update['commcare-version']);
            }
            if (COMMCAREHQ.app_manager.fetchAndShowFormValidation) {
                COMMCAREHQ.app_manager.fetchAndShowFormValidation();
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
	                    unsavedMessage: "You have unsaved changes",
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
                                COMMCAREHQ.app_manager.module_view.requires_case_details(data['case_list-show'])
                            }
	                    }
	                }).ui.appendTo($buttonHolder);
                });
            }());
        }

        $('#form-tabs').show();
        $('#forms').tab('show');

        $('.sortable .sort-action').addClass('sort-disabled');
        $('.drag_handle').addClass(COMMCAREHQ.icons.GRIP);
        $('.sortable').each(function () {
            if ($(this).children().not('.sort-disabled').size() < 2) {
                var $sortable = $(this);
                $('.drag_handle', this).each(function () {
                    if ($(this).closest('.sortable')[0] === $sortable[0]) {
                        $(this).removeClass('drag_handle').hide();
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
                            $sortable.find('.drag_handle').css('color', 'transparent').removeClass('drag_handle');
                            $sortable.sortable('option', 'disabled', true);
                            if ($form.find('input[name="ajax"]').first().val() === "true") {
                                resetIndexes($sortable);
                                $.post($form.attr('action'), $form.serialize(), function (data) {
                                    COMMCAREHQ.app_manager.updateDOM(JSON.parse(data).update);
                                    // re-enable sortable
                                    $sortable.sortable('option', 'disabled', false);
                                    $sortable.find('.drag_handle').show(1000);
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
            var lang = $(this).find('option:selected').attr('value');
            $(document).attr('location', window.location.href + (window.location.search ? '&' : '?') + 'lang=' + lang);
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

        $('.index').change(function () {
            // make sure that column_id changes when index changes (after drag-drop)
            $(this).closest('tr').find('[name="index"]').val($(this).text());
        }).trigger('change');

        COMMCAREHQ.app_manager.commcareVersion.subscribe(function () {
            $('.commcare-feature').each(function () {
                var version = '' + $(this).data('since-version') || '1.1',
                    upgradeMessage = $('<span class="upgrade-message"/>'),
                    area = $(this);

                if (COMMCAREHQ.app_manager.checkCommcareVersion(version)) {
                    area.find('upgrade-message').remove();
                    area.find('*:not(".hidden")').show();
                } else {
                    area.find('*').hide();
                    upgradeMessage.append(
                        $('<i></i>').addClass('icon-arrow-left')
                    ).append(
                        $('<span></span>').text(' Requires CommCare ' + version)
                    ).appendTo(area);
                }
            });
        });
        COMMCAREHQ.app_manager.setCommcareVersion(args.commcareVersion);
    };
}());