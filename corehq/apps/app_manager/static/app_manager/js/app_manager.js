/* globals hqDefine django hqImport */
hqDefine('app_manager/js/app_manager', function () {
    'use strict';
    var module = hqImport("hqwebapp/js/main").eventize({});
    var _private = {};
    _private.appendedPageTitle = "";
    _private.prependedPageTitle = "";

    module.setCommcareVersion = function (version) {
        module.commcareVersion(version);
    };

    module.setAppendedPageTitle = function (appendedPageTitle) {
        _private.appendedPageTitle = appendedPageTitle;
    };
    module.setPrependedPageTitle = function (prependedPageTitle, noDivider) {
        _private.prependedPageTitle = prependedPageTitle;
        if (!noDivider) {
            _private.prependedPageTitle += " - ";
        }
    };

    module.updatePageTitle = function (pageTitle) {
        var newTitle = pageTitle;
        if (_private.appendedPageTitle) {
            newTitle += " - " + _private.appendedPageTitle;
        }
        if (_private.prependedPageTitle) {
            newTitle = _private.prependedPageTitle + newTitle;
        }
        document.title = newTitle + " - CommCare HQ";
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

    module.updateDOM = function (update) {
        if (update.hasOwnProperty('app-version')) {
            var appVersion = update['app-version'];
            $('.variable-version').text(appVersion);
        }
        if (update.hasOwnProperty('commcare-version')) {
            module.setCommcareVersion(update['commcare-version']);
        }
        if (module.fetchAndShowFormValidation) {
            module.fetchAndShowFormValidation();
        }
        hqImport("hqwebapp/js/main").updateDOM(update);
    };

    module.setupValidation = function (validationUrl) {
        module.fetchAndShowFormValidation = function () {
            $.getJSON(validationUrl, function (data) {
                $('#build_errors').html(data.error_html);
            });
        };
        if ($.cookie('suppress_build_errors')) {
            $.removeCookie('suppress_build_errors', { path: '/' });
        } else {
            module.fetchAndShowFormValidation();
        }
    };

    module.init = function (args) {
        _initCommcareVersion(args);
        _initSaveButtons();
        _initMenuItemSorting();
        _initResponsiveMenus();
        _initAddItemPopovers();
    };

    /**
     * Initialize the commcare version and check whether there is a later
     * version of CommCare that is available.
     * @param args
     * @private
     */
    var _initCommcareVersion = function (args) {
        module.commcareVersion = ko.observable();
        module.latestCommcareVersion = ko.observable();
        module.latestCommcareVersion(args.latestCommcareVersion);
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

    /**
     * Initialize the add item popover in the app v2 navigation menu. Make sure
     * the icons in the popover properly trigger the add item form and that
     * clicking away from the popover elsewhere on the screen closes it.
     * @private
     */
    var _initAddItemPopovers = function () {
        $('.js-add-new-item').popover({
            title: django.gettext("Add"),
            container: 'body',
            content: function () {
                var slug = $(this).data("slug"),
                    template = $('.js-popover-template-add-item-content[data-slug="' + slug + '"]').text();
                return _.template(template)($(this).data());
            },
            html: true,
            trigger: 'manual',
            placement: 'right',
            template: $('#js-popover-template-add-item').text(),
        }).on('show.bs.popover', function () {
            // Close any other open popover
            $('.js-add-new-item').not($(this)).popover('hide');
        }).one('shown.bs.popover', function () {
            var pop = this;
            $('.popover-additem').on('click', function (e) {
                $(pop).popover('hide');
                var dataType = $(e.target).closest('button').data('type'),
                    isForm =  $(e.target).closest('button').data('form-type') !== undefined,
                    stopSubmit = $(e.target).closest('button').data('stopsubmit') === 'yes',
                    $form;

                if (stopSubmit) return;

                if (isForm) {
                    var caseAction =  $(e.target).closest('button').data('case-action'),
                        $popoverContent = $(e.target).closest(".popover-content > *"),
                        moduleId = $popoverContent.data("module-unique-id"),
                        $trigger = $('.js-add-new-item[data-module-unique-id="' + moduleId + '"]');

                    $form = $popoverContent.find("form");
                    $form.find("input[name='case_action']").val(caseAction);
                    $form.find("input[name='form_type']").val(dataType);
                    if (!$form.data('clicked')) {
                        $form.data('clicked', 'true');
                        $trigger.find(".fa-plus").removeClass("fa-plus").addClass("fa fa-refresh fa-spin");
                        $form.submit();
                    }

                } else {
                    $('#new-module-type').val(dataType);
                    if ($(e.target).closest('button').data('stopsubmit') !== 'yes') {
                        $form = $('#new-module-form');
                        if (!$form.data('clicked')) {
                            $form.data('clicked', 'true');
                            $('.new-module-icon').removeClass().addClass("fa fa-refresh fa-spin");
                            if (dataType === "case") {
                                hqImport('analytix/js/google').track.event("Added Case List Menu");
                                hqImport('analytix/js/kissmetrix').track.event("Added Case List Menu");
                            } else if (dataType === "survey") {
                                hqImport('analytix/js/google').track.event("Added Surveys Menu");
                                hqImport('analytix/js/kissmetrix').track.event("Added Surveys Menu");
                            }
                            $form.submit();
                        }
                    }
                }
            });
        }).on('click', function (e) {
            e.preventDefault();
            $(this).popover('show');
        });

        // Close any open popover when user clicks elsewhere on the page
        $('body').click(function (event) {
            if (!($(event.target).hasClass('appnav-add') || $(event.target).hasClass('popover-additem-option') || $(event.target).hasClass('fa'))) {
                $('.js-add-new-item').popover('hide');
            }
        });
    };

    /**
     * For all the navigation links marked as responsive, make sure they hide
     * the main content element as soon as they are clicked to show the "loading"
     * animation and indicate to the user that something is going on.
     * @private
     */
    var _initResponsiveMenus = function () {
        $(document).on('click', '.appnav-responsive', function (e) {
            if (!e || (!e.metaKey && !e.ctrlKey && !e.which !== 2)) {
                // TODO doesn't handle vellum with saved changes.
                $('#js-appmanager-body.appmanager-settings-content').addClass('hide');
            }
        });
    };

    /**
     * Initialize sorting in the app manager menu.
     * @private
     */
    var _initMenuItemSorting = function () {
        function updateRelatedTags($elem, name, value) {
            var relatedTags = $elem.find("[data-" + name + "]");
            _.each(relatedTags, function (related) {
                $(related).data(name, value);
            });
        }
        function resetIndexes($sortable) {
            var parentVar = $sortable.data('parentvar');
            var parentValue = $sortable.closest("[data-indexVar='" + parentVar + "']").data('index');
            _.each($sortable.find('> .js-sorted-li'), function (elem, i) {
                $(elem).data('index', i);
                var indexVar = $(elem).data('indexvar');
                updateRelatedTags($(elem), indexVar, i);
                if (parentVar) {
                    $(elem).data(parentVar, parentValue);
                    updateRelatedTags($(elem), parentVar, parentValue);
                }
            });
        }

        $('.sortable .sort-action').addClass('sort-disabled');
        $('.drag_handle').addClass('fa fa-arrows-v');

        $('.js-appnav-drag-module').on('mouseenter', function () {
            $(this).closest('.js-sorted-li').addClass('appnav-highlight');
        }).on('mouseleave', function () {
            $(this).closest('.js-sorted-li').removeClass('appnav-highlight');
        });

        // Initialize sorting behavior for both modules and forms
        $('.sortable').each(function () {
            var $sortable = $(this);
            var sortingForms = $sortable.hasClass('sortable-forms');
            var options = {
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
                        toModuleId = parseInt($sortable.parents('.edit-module-li').data('index'), 10),
                        movingToNewModule = false,
                        $form;

                    // if you're moving modules or moving forms within the same module, use this logic to find to and from
                    if (!sortingForms || toModuleId === parseInt(ui.item.data('moduleid'), 10)) {
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
                            if (parseInt($(this).data('moduleid'), 10) !== toModuleId) {
                                movingToNewModule = true;
                                to = i;
                                from = parseInt(ui.item.data('index'), 10);
                                return false;
                            }
                        });
                    }

                    if (movingToNewModule || to !== from) {
                        var fromModuleId = parseInt(ui.item.data('moduleid'), 10);
                        $form = $(this).find('> .sort-action form');
                        $form.find('[name="from"], [name="to"]').remove();
                        $form.append('<input type="hidden" name="from" value="' + from.toString() + '" />');
                        $form.append('<input type="hidden" name="to"   value="' + to.toString() + '" />');
                        if (sortingForms) {
                            $form.append('<input type="hidden" name="from_module_id" value="' + fromModuleId.toString() + '" />');
                            $form.append('<input type="hidden" name="to_module_id"   value="' + toModuleId.toString() + '" />');
                        }

                        resetIndexes($sortable);
                        if (fromModuleId !== toModuleId) {
                            var $parentSortable = $sortable.parents(".sortable"),
                                $fromSortable = $parentSortable.find("[data-index=" + fromModuleId + "] .sortable");
                            resetIndexes($fromSortable);
                        }
                        $.ajax($form.attr('action'), {
                            method: 'POST',
                            data: $form.serialize(),
                            success: function () {
                                hqImport('hqwebapp/js/alert_user').alert_user(gettext("Moved successfully."), "success");
                            },
                            error: function (xhr) {
                                hqImport('hqwebapp/js/alert_user').alert_user(xhr.responseJSON.error, "danger");
                            },
                        });
                        hqImport("app_manager/js/menu").setPublishStatus(true);
                    }
                },
            };
            if (sortingForms) {
                options["connectWith"] = '.sortable-forms';
            }
            $(this).sortable(options);
        });
        $('.sort-action').hide();
    };

    /**
     * Initialize the save buttons on the various tabs and forms.
     * @private
     */
    var _initSaveButtons = function () {
        var $forms = $('.save-button-form');
        $forms.each(function () {
            var $form = $(this),
                $buttonHolder = $form.find('.save-button-holder'),
                button = hqImport("hqwebapp/js/main").initSaveButtonForm($form, {
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
                            var requiresCaseDetails = hqImport('app_manager/js/details/screen_config').state.requiresCaseDetails;
                            requiresCaseDetails(data['case_list-show']);
                        }
                        $form.trigger('saved-app-manager-form');
                    },
                });
            button.ui.appendTo($buttonHolder);
            $buttonHolder.data('button', button);
            hqImport("app_manager/js/section_changer").attachToForm($form);
        });
    };

    return module;
});
