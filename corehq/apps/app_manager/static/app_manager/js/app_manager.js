'use strict';
hqDefine('app_manager/js/app_manager', function () {
    var initialPageData = hqImport("hqwebapp/js/initial_page_data");
    var module = hqImport("hqwebapp/js/bootstrap3/main").eventize({});
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
        if (_.has(update, 'app-version')) {
            var appVersion = update['app-version'];
            $('.variable-version').text(appVersion);
        }
        if (_.has(update, 'commcare-version')) {
            module.setCommcareVersion(update['commcare-version']);
        }
        if (module.fetchAndShowFormValidation) {
            module.fetchAndShowFormValidation();
        }
        hqImport("hqwebapp/js/bootstrap3/main").updateDOM(update);
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
                        $('<i></i>').addClass('fa fa-arrow-left')
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
            title: gettext("Add"),
            container: 'body',
            sanitize: false,
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

                if (stopSubmit) {
                    return;
                }

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
        var MODULE_SELECTOR = ".appmanager-main-menu .module";
        if (!hqImport('hqwebapp/js/toggles').toggleEnabled('LEGACY_CHILD_MODULES')) {
            nestChildModules();
            initChildModuleUpdateListener();
        }
        if (modulesWereReordered()) {
            promptToSaveOrdering();
        } else {
            initDragHandles();
            $('.sortable').each(function () {
                initSortable($(this));
            });
        }

        function initDragHandles() {
            var $scope = $(".appmanager-main-menu");
            $scope.find('.drag_handle').addClass('fa-solid fa-up-down');
            $scope.find('.js-appnav-drag-module').on('mouseenter', function () {
                $(this).closest('.js-sorted-li').addClass('appnav-highlight');
            }).on('mouseleave', function () {
                $(this).closest('.js-sorted-li').removeClass('appnav-highlight');
            });
        }
        function nestChildModules() {
            var modulesByUid = getModulesByUid(),
                childModules = [];
            $(MODULE_SELECTOR).each(function (index, element) {
                // Set index here so we know whether we've rearranged anything
                $(element).data('index', index);
                if ($(element).data('rootmoduleuid')) {
                    childModules.push(element);
                }
            });
            _.each(childModules, function (childModule) {
                var parent = modulesByUid[$(childModule).data('rootmoduleuid')];
                if (!parent) {
                    moveModuleToBottom(childModule);
                } else {
                    addChildModuleToParent(childModule, parent);
                }
            });
        }
        function getModulesByUid() {
            var modulesByUid = {};
            $(MODULE_SELECTOR).each(function (index, element) {
                modulesByUid[ $(element).data('uid') ] = element;
            });
            return modulesByUid;
        }
        function addChildModuleToParent(childModule, parent) {
            var childList = $(parent).find("ul.child-modules");
            if (childList.length === 0) {
                childList = $('<ul class="appnav-menu child-modules sortable"></ul>');
                $(parent).append(childList);
            }
            childList.append(childModule);
        }
        function moveModuleToBottom(module) {
            $("ul.appmanager-main-menu").append(module);
        }
        function initChildModuleUpdateListener() {
            // If a child module is created or removed, update the sidebar
            $('#module-settings-form').on('saved-app-manager-form', function () {
                var $parentModuleSelector = $(this).find('select[name=root_module_id]');
                if ($parentModuleSelector.length === 0) {
                    return;
                }
                var modulesByUid = getModulesByUid(),
                    module = modulesByUid[$(this).data('moduleuid')],
                    oldRoot = $(module).data('rootmoduleuid') || null,
                    newRoot = $parentModuleSelector.val() || null;

                if (newRoot !== oldRoot) {
                    $(module).data('rootmoduleuid', newRoot);
                    if (!newRoot) {
                        moveModuleToBottom(module);
                    } else {
                        addChildModuleToParent(module, modulesByUid[newRoot]);
                    }
                    rearrangeModules($(module));
                    resetIndexes();
                }
            });
        }
        function modulesWereReordered() {
            return _.some($(MODULE_SELECTOR), function (element, index) {
                return index !== $(element).data('index');
            });
        }
        function promptToSaveOrdering() {
            $("#reorder_modules_modal").modal('show');
        }
        function initSortable($sortable) {
            var options = {
                handle: '.drag_handle ',
                items: ">*:not(.sort-disabled)",
                update: function (e, ui) { updateAfterMove(e, ui, $sortable); },
            };
            if ($sortable.hasClass('sortable-forms')) {
                options["connectWith"] = '.sortable-forms';
            }
            $sortable.sortable(options);
        }
        function updateAfterMove(e, ui, $sortable) {
            // because the event is triggered on both sortables when moving between one sortable list to
            // another, do a check to see if this is the sortable list we're moving the item to
            if ($sortable.find(ui.item).length < 1) { return; }

            if ($sortable.hasClass('sortable-forms')) {
                rearrangeForms(ui, $sortable);
            } else {
                rearrangeModules(ui.item);
            }
            resetIndexes();
        }
        function rearrangeForms(ui, $sortable) {
            var url = initialPageData.reverse('rearrange', 'forms'),
                toModuleUid = $sortable.parents('.edit-module-li').data('uid'),
                fromModuleUid = ui.item.data('moduleuid'),
                from = ui.item.data('index'),
                to = _.findIndex($sortable.children().not('.sort-disabled'), function (form) {
                    return $(form).data('uid') === ui.item.data('uid');
                });

            if (to !== from || toModuleUid !== fromModuleUid) {
                saveRearrangement(url, from, to, fromModuleUid, toModuleUid);
            }
        }
        function rearrangeModules($module) {
            var url = initialPageData.reverse('rearrange', 'modules'),
                from = $module.data('index'),
                to = _.findIndex($(MODULE_SELECTOR), function (module) {
                    return $(module).data('uid') === $module.data('uid');
                });

            if (to !== from) {
                saveRearrangement(url, from, to);
            }
        }
        function resetIndexes() {
            $(MODULE_SELECTOR).each(function (index, module) {
                $(module).data('index', index);
                $(module).children("ul.sortable-forms").first().children("li").each(function (index, form) {
                    $(form).data('index', index);
                    $(form).data('moduleuid', $(module).data('uid'));
                });
            });
        }
        function saveRearrangement(url, from, to, fromModuleUid, toModuleUid) {
            var data = {
                from: from,
                to: to,
                from_module_uid: fromModuleUid,
                to_module_uid: toModuleUid,
            };
            $.ajax(url, {
                method: 'POST',
                data: data,
                success: function () {
                    hqImport('hqwebapp/js/bootstrap3/alert_user').alert_user(gettext("Moved successfully."), "success");
                },
                error: function (xhr) {
                    hqImport('hqwebapp/js/bootstrap3/alert_user').alert_user(xhr.responseJSON.error, "danger");
                },
            });
            hqImport("app_manager/js/menu").setPublishStatus(true);
        }

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
                button = hqImport("hqwebapp/js/bootstrap3/main").initSaveButtonForm($form, {
                    unsavedMessage: gettext("You have unsaved changes"),
                    success: function (data) {
                        var key;
                        module.updateDOM(data.update);
                        for (key in data.corrections) {
                            if (_.has(data.corrections, key)) {
                                $form.find('[name="' + key + '"]').val(data.corrections[key]);
                                $(document).trigger('correction', [key, data.corrections[key]]);
                            }
                        }
                        if (_.has(data, 'redirect')) {
                            window.location = data.redirect;
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
