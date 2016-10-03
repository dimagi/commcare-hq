/*globals hqDefine */
hqDefine('app_manager/js/app_manager.js', function () {
    'use strict';
    var module = eventize({});

    module.setCommcareVersion = function (version) {
        module.commcareVersion(version);
    };
    module.checkCommcareVersion = function (version) {
        return module.versionGE(module.commcareVersion(), version);
    };
    module.checkAreWeThereYet = function (version) {
        if (!module.latestCommcareVersion()) {
            // We don't know the latest version. Assume this version has arrived
            return true;
        } else {
            return module.versionGE(module.latestCommcareVersion(), version);
        }
    };
    module.versionGE = function (commcareVersion1, commcareVersion2) {
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
    };
    module.init = function (args) {
        var appVersion = args.appVersion;
        module.commcareVersion = ko.observable();
        module.latestCommcareVersion = ko.observable();
        module.latestCommcareVersion(args.latestCommcareVersion);

        function updateDOM(update) {
            if (update.hasOwnProperty('app-version')) {
                appVersion = update['app-version'];
                $('.variable-version').text(appVersion);
            }
            if (update.hasOwnProperty('commcare-version')) {
                module.setCommcareVersion(update['commcare-version']);
            }
            if (module.fetchAndShowFormValidation) {
                module.fetchAndShowFormValidation();
            }
            COMMCAREHQ.updateDOM(update);
        }
        module.updateDOM = updateDOM;
        function getVar(name) {
            var r = $('input[name="' + name + '"]').first().val();
            return JSON.parse(r);
        }
        function resetIndexes($sortable) {
            var $sortables = $sortable.children.get(),
                i;
            for (i in $sortables) {
                if ($sortables.hasOwnProperty(i)) {
                    $($sortables[i]).data('index', i);
                }
            }
        }
        COMMCAREHQ.resetIndexes = resetIndexes;

        (function () {
            var $forms = $('.save-button-form');
            $forms.each(function () {
                var $form = $(this),
                    $buttonHolder = $form.find('.save-button-holder'),
                    button = COMMCAREHQ.SaveButton.initForm($form, {
                        unsavedMessage: gettext("You have unsaved changes"),
                        success: function (data) {
                            var key;
                            module.updateDOM(data.update);
                            for (key in data.corrections) {
                                if (data.corrections.hasOwnProperty(key)) {
                                    $form.find('[name="' + key + '"]').val(data.corrections[key]);
                                    $(document).trigger('correction', [key, data.corrections[key]]);
                                }
                            }
                            if (data.hasOwnProperty('case_list-show') &&
                                    module.hasOwnProperty('module_view')) {
                                var requires_case_details = hqImport('app_manager/js/detail-screen-config.js').state.requires_case_details;
                                requires_case_details(data['case_list-show']);
                            }
                        }
                    });
                button.ui.appendTo($buttonHolder);
                $buttonHolder.data('button', button);
            });
        }());

        $('#form-tabs').show();
        $('#forms').tab('show');

        $('.sortable .sort-action').addClass('sort-disabled');
        $('.drag_handle').addClass(COMMCAREHQ.icons.GRIP);
        $('.sortable').each(function () {
            var min_elem = $(this).hasClass('sortable-forms') ? 1 : 2;
            if ($(this).children().not('.sort-disabled').length < min_elem) {
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
            var sorting_forms = $sortable.hasClass('sortable-forms');
            var min_elem = $(this).hasClass('sortable-forms') ? 0 : 1;
            if ($(this).children().not('.sort-disabled').length > min_elem) {
                var init_dict = {
                    handle: '.drag_handle ',
                    items: ">*:not(.sort-disabled)",
                    update: function (e, ui) {
                        // because the event is triggered on both sortables when moving between one sortable list to
                        // another, do a check to see if this is the sortable list we're moving the item to
                        if ($sortable.find(ui.item).length < 1) {
                            return;
                        }

                        var to = -1,
                            from = -1,
                            to_module_id = parseInt($sortable.parents('.edit-module-li').data('index'), 10),
                            moving_to_new_module = false,
                            $form;

                        // if you're moving modules or moving forms within the same module, use this logic to find to and from
                        if (!sorting_forms || to_module_id === parseInt(ui.item.data('moduleid'), 10)) {
                            $(this).children().not('.sort-disabled').each(function (i) {
                                var index = parseInt($(this).data('index'), 10);
                                if (from !== -1) {
                                    if (from === index) {
                                        to = i;
                                        return false;
                                    }
                                }
                                if (i !== index) {
                                    if (i + 1 === index) {
                                        from = i;
                                    } else {
                                        to = i;
                                        from = index;
                                        return false;
                                    }
                                }
                            });
                        } else { //moving forms to a new submodule
                            $(this).children().not('.sort-disabled').each(function (i) {
                                if (parseInt($(this).data('moduleid'), 10) !== to_module_id) {
                                    moving_to_new_module = true;
                                    to = i;
                                    from = parseInt(ui.item.data('index'), 10);
                                    return false;
                                }
                            });
                        }

                        if (moving_to_new_module || to !== from) {
                            var from_module_id = parseInt(ui.item.data('moduleid'), 10);
                            $form = $(this).find('> .sort-action form');
                            $form.find('[name="from"], [name="to"]').remove();
                            $form.append('<input type="hidden" name="from" value="' + from.toString() + '" />');
                            $form.append('<input type="hidden" name="to"   value="' + to.toString()   + '" />');
                            if (sorting_forms) {
                                $form.append('<input type="hidden" name="from_module_id" value="' + from_module_id.toString() + '" />');
                                $form.append('<input type="hidden" name="to_module_id"   value="' + to_module_id.toString()   + '" />');
                            }

                            // disable sortable
                            $sortable.find('.drag_handle').css('color', 'transparent').removeClass('drag_handle');
                            $sortable.sortable('option', 'disabled', true);
                            if ($form.find('input[name="ajax"]').first().val() === "true") {
                                resetIndexes($sortable);
                                $.post($form.attr('action'), $form.serialize(), function (data) {
                                    module.updateDOM(JSON.parse(data).update);
                                    // re-enable sortable
                                    $sortable.sortable('option', 'disabled', false);
                                    $sortable.find('.drag_handle').show(1000);
                                });
                            } else {
                                $form.submit();
                            }
                        }
                    }
                };
                if (sorting_forms) {
                    init_dict["connectWith"] = '.sortable-forms';
                }
                $(this).sortable(init_dict);
            }
        });
        $('.sort-action').hide();

        $('select.applications').change(function () {
            var url = $(this).find('option:selected').attr('value');
            $(document).attr('location', url);
        });
        $('#langs select').change(function () {
            var lang = $(this).find('option:selected').attr('value');
            $(document).attr('location', window.location.href + (window.location.search ? '&' : '?') + 'lang=' + lang);
        });

        // Auto set input and select values according to the following 'div.immutable'
        $('select').each(function () {
            var val = $(this).next('div.immutable').text();
            if (val) {
                $(this).find('option').prop('selected', false);
                $(this).find('option[value="' + val + '"]').prop('selected', true);
            }
        });
        $('input[type="text"]').each(function () {
            var val = $(this).next('div.immutable').text();
            if (val) {
                $(this).attr('value', val);
            }
        });

        $('.new-module').on('click', function (e) {
            e.preventDefault();
            var dataType = $(this).data('type');
            $('#new-module-type').val(dataType);
            var form = $('#new-module-form');
            if (!form.data('clicked')) {
                form.data('clicked', 'true');
                $('.new-module-icon').removeClass().addClass("fa fa-refresh icon-spin");
                form.submit();
            }
        });

        if (COMMCAREHQ.toggleEnabled('ONBOARDING_PROTOTYPE')) {
            $('.new-form').on('click', function (e) {
                e.preventDefault();
                var $a = $(this),
                    $form = $a.siblings("form"),
                    action = $a.data("case-action");
                $form.find("input[name='case_action']").val(action);
                $form.find("input[name='name']").val(action === "update" ? "Followup" : "Survey");
                if (!$form.data('clicked')) {
                    $form.data('clicked', 'true');
                    $a.find(".fa-plus").removeClass("fa-plus").addClass("fa fa-refresh icon-spin");
                    $form.submit();
                }
            });
        }

        module.commcareVersion.subscribe(function () {
            $('.commcare-feature').each(function () {
                // .attr() keeps zero intact in 2.10, data() doesn't
                var version = '' + $(this).attr('data-since-version') || '1.1',
                    upgradeMessage = $('<span class="upgrade-message"/>'),
                    area = $(this);

                if (module.checkCommcareVersion(version)) {
                    area.find('upgrade-message').remove();
                    area.find('*:not(".hide")').show();
                } else if (!module.checkAreWeThereYet(version)) {
                    area.parent().hide();
                } else {
                    area.find('*').hide();
                    upgradeMessage.append(
                        $('<i></i>').addClass('fa').addClass('fa-arrow-left')
                    ).append(
                        $('<span></span>').text(' Requires CommCare ' + version)
                    ).appendTo(area);
                }
            });
        });
        module.setCommcareVersion(args.commcareVersion);
    };

    module.setupValidation = function (validation_url) {
        module.fetchAndShowFormValidation = function () {
            $.getJSON(validation_url, function (data) {
                $('#build_errors').html(data.error_html);
            });
        };
        if ($.cookie('suppress_build_errors')) {
            $.removeCookie('suppress_build_errors', { path: '/' });
        } else {
            module.fetchAndShowFormValidation();
        }
    };
    return module;
});
