import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import hqLayout from "hqwebapp/js/layout";
import toggles from "hqwebapp/js/toggles";
import uiElementLangcodeButton from "hqwebapp/js/ui_elements/ui-element-langcode-button";
import google from "analytix/js/google";
import noopMetrics from "analytix/js/noopMetrics";
import alertUser from "hqwebapp/js/bootstrap3/alert_user";
import main from "hqwebapp/js/bootstrap3/main";
import menu from "app_manager/js/menu";
import previewApp from "app_manager/js/preview_app";
import sectionChanger from "app_manager/js/section_changer";
import "hqwebapp/js/components/inline_edit";  // app, menu, and form names and comments all use these
import "select2/dist/js/select2.full.min";

var module = main.eventize({});
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
    main.updateDOM(update);
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

module.valueIncludeInvalidCharacters = function (valueNoSpaces) {
    return !valueNoSpaces.match(/^[\w-]*$/g);
};

module.invalidCharErrorMsg = gettext("Case types can only include the characters a-z, 0-9, '-' and '_'");

module.valueIsReservedWord = function (valueNoSpaces) {
    return valueNoSpaces === 'commcare-user' || valueNoSpaces === 'user-owner-mapping-case';
};

module.reservedWordErrorMsg = gettext("This is a reserved case type. Please choose another name.");

module.deprecatedCaseTypeErrorMsg = gettext("This case type has been deprecated in the Data Dictionary.");

module.init = function (args) {
    _initCommcareVersion(args);
    _initSaveButtons();
    _initMenuItemSorting();
    _initResponsiveMenus();
    _initAddItemPopovers();
    _initNewModuleOptionClicks();
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
                    $('<i></i>').addClass('fa fa-arrow-left'),
                ).append(
                    $('<span></span>').text(' Requires CommCare ' + version),
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
            var template = $('.js-popover-template-add-item-content[data-slug="form"]').text();
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
                stopSubmit = $(e.target).closest('button').data('stopsubmit') === 'yes',
                $form;

            if (stopSubmit) {
                return;
            }

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
    if (!toggles.toggleEnabled('LEGACY_CHILD_MODULES')) {
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
                alertUser.alert_user(gettext("Moved successfully."), "success");
            },
            error: function (xhr) {
                alertUser.alert_user(xhr.responseJSON.error, "danger");
            },
        });
        menu.setPublishStatus(true);
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
            button = main.initSaveButtonForm($form, {
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
        sectionChanger.attachToForm($form);
    });
};

$(function () {
    const app = initialPageData.get('app_subset');
    module.init({
        appVersion: app.version || -1,
        commcareVersion: String(app.commcare_minor_release),
        latestCommcareVersion: initialPageData.get('latest_commcare_version') || null,
    });

    $('.btn-langcode-preprocessed').each(function () {
        uiElementLangcodeButton.new($(this), $(this).text());
        if ($(this).hasClass('langcode-input')) {
            var $langcodeInput = $(this).parent().find("input");
            var that = this;
            if ($langcodeInput) {
                $langcodeInput.change(function () {
                    if ($(this).val() === "") {
                        $(that).show();
                    } else {
                        $(that).hide();
                    }
                });
            }
        }
    });

    $('[data-toggle="tooltip"]').tooltip();

    // https://github.com/twitter/bootstrap/issues/6122
    // this is necessary to get popovers to be able to extend
    // outside the borders of their containing div
    //
    // http://manage.dimagi.com/default.asp?183618
    // Firefox 40 considers hovering on a select a mouseleave event and thus kills the select
    // dropdown. The focus and blur events are to ensure that we do not trigger overflow hidden
    // if we are in a select
    var inSelectElement = false,
        $tabContent = $('.tab-content');
    $tabContent.css('overflow', 'visible');
    $tabContent.on('mouseenter', '.collapse', function () {
        $(this).css('overflow','visible');
    });
    $tabContent.on('mouseleave', '.collapse', function () {
        if (inSelectElement) { return; }
        $(this).css('overflow','hidden');
    });
    $tabContent.on('focus', '.collapse', function () {
        inSelectElement = true;
    });
    $tabContent.on('blur', '.collapse', function () {
        inSelectElement = false;
    });

    // Handling for popup displayed when accessing a deleted app
    $('#deleted-app-modal').modal({
        backdrop: 'static',
        keyboard: false,
        show: true,
    }).on('hide.bs.modal', function () {
        window.location = initialPageData.reverse('dashboard_default');
    });

    // Set up app preview
    previewApp.initPreviewWindow();

    // Hide fancy app manager loading animation
    $('.appmanager-content').fadeIn();
    $('.appmanager-loading').fadeOut();

    hqLayout.setIsAppbuilderResizing(true);
});

var _initNewModuleOptionClicks = function () {
    var self = {};
    self.deprecatedCaseTypes = ko.observableArray();

    $('.new-module-option').on('click', function () {
        var moduleType = $(this).data('type');
        $('#new-module-type').val(moduleType);
        var $form = $('#new-module-form');

        if (moduleType === "case") {
            $('#add-new-module-modal').modal('hide');
            $('#define-case-type-modal').modal('show');
        } else {
            if (moduleType === "survey") {
                google.track.event("Added Surveys Menu");
                noopMetrics.track.event("Added Surveys Menu");
            }
            $('.new-module-icon').removeClass().addClass("fa fa-refresh fa-spin");
            $('#add-new-module-modal').modal('hide');
            $form.submit();
        }
    });

    $('#define-case-type-modal').on('show.bs.modal', function () {
        var $caseType = $('#new-case-type-dropdown');
        if (!$caseType.data('select2')) {
            $caseType.select2({
                tags: true,
                placeholder: gettext("Add a new case type or use an existing one"),
                allowClear: true,
                width: '100%',
                dropdownParent: $('#define-case-type-modal'),
                createTag: function (params) {
                    // Replace spaces with underscore
                    var term = params.term.replace(/ /g, '_');
                    return {
                        id: term,
                        text: term,
                    };
                },
            });

            // Write ajax here not in the Select2 init so that we send ajax request only once
            $.ajax({
                method: 'GET',
                url: initialPageData.reverse('all_case_types'),
                success: function (data) {
                    var existingCaseTypes = data.existing_case_types;
                    self.deprecatedCaseTypes(data.deprecated_case_types);

                    // Add existing case types as options
                    existingCaseTypes.forEach(function (caseType) {
                        var option = new Option(caseType, caseType, false, false);
                        $caseType.append(option);
                    });
                },
            });

            $caseType.on('change', function () {
                var valueNoSpaces = $(this).val();
                var $formGroup = $(this).closest('.form-group');
                var $help = $('#new-case-type-help');
                var $error = $('#new-case-type-error');
                var $createBtn = $('#case-type-create-btn');

                // Reset error states
                $formGroup.removeClass('has-error');
                $help.show();
                $error.hide();
                $createBtn.prop('disabled', false);

                if (!valueNoSpaces) {
                    $createBtn.prop('disabled', true);
                    return;
                }

                function displayError(errorMsg) {
                    $formGroup.addClass('has-error');
                    $error.text(errorMsg);
                    $error.show();
                    $help.hide();
                    $createBtn.prop('disabled', true);
                }

                if (module.valueIncludeInvalidCharacters(valueNoSpaces)) {
                    displayError(module.invalidCharErrorMsg);
                    return;
                }

                if (module.valueIsReservedWord(valueNoSpaces)) {
                    displayError(module.reservedWordErrorMsg);
                    return;
                }

                if (self.deprecatedCaseTypes().includes(valueNoSpaces)) {
                    displayError(module.deprecatedCaseTypeErrorMsg);
                    return;
                }
            });
        }
    });

    // Handle "Create Application" button click
    $('#case-type-create-btn').on('click', function () {
        google.track.event("Added Case List Menu");
        noopMetrics.track.event("Added Case List Menu");

        var $caseTypeInput = $('#new-case-type-dropdown');
        var value = $caseTypeInput.val();

        var $form = $('#new-module-form');
        // This input element lives in appnav_menu.html, so we need to update it here
        let newCaseTypeHiddenInput = $('#new-case-type');
        newCaseTypeHiddenInput.val(value);

        $('.new-module-icon').removeClass().addClass("fa fa-refresh fa-spin");
        $('#define-case-type-modal').modal('hide');
        $form.submit();
    });

    // Handle "Go Back" button click
    $('#case-type-go-back-btn').on('click', function () {
        $('#define-case-type-modal').modal('hide');
        $('#add-new-module-modal').modal('show');
    });

    // Clear selection when modal is hidden
    $('#define-case-type-modal').on('hidden.bs.modal', function () {
        $('#new-case-type-dropdown').val(null).trigger('change');
    });

    var hoverHelpTexts = {
        survey: {
            title: gettext("What is a Survey Menu?"),
            content: gettext("Surveys are used to collect independent forms that do not need to be tracked over time. Common examples include satisfaction surveys or anonymous feedback forms."),
        },
        case: {
            title: gettext("What is a Case List?"),
            content: gettext("Case Lists are used to register and track related data (cases) over time. This data can be referenced in other forms and by other cases. Common examples include maternal health, student attendance, or crop monitoring."),
        },
    };

    $('.new-module-option').each(function () {
        var type = $(this).data('type');
        if (hoverHelpTexts[type]) {
            $(this).popover({
                title: hoverHelpTexts[type].title,
                content: hoverHelpTexts[type].content,
                trigger: 'hover',
                placement: 'bottom',
                container: 'body',
                html: true,
            });
        }
    });

};

export default module;
