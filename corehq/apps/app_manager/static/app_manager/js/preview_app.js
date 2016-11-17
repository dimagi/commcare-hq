/* globals $ */
/* globals window */

hqDefine('app_manager/js/preview_app.js', function() {
    'use strict';
    var module = {};
    var _private = {};

    module.SELECTORS = {
        BTN_TOGGLE_PREVIEW: '.js-preview-toggle',
        PREVIEW_WINDOW: '#js-appmanager-preview',
        PREVIEW_WINDOW_IFRAME: '#js-appmanager-preview iframe',
        APP_MANAGER_BODY: '#js-appmanager-body',
        PREVIEW_ACTION_TEXT_SHOW: '.js-preview-action-show',
        PREVIEW_ACTION_TEXT_HIDE: '.js-preview-action-hide',
        BTN_REFRESH: '.js-preview-refresh',
    };

    module.EVENTS = {
        RESIZE: 'previewApp.resize',
    };

    module.POSITION = {
        FIXED: 'fixed',
        ABSOLUTE: 'absolute',
    };

    module.DATA = {
        OPEN: 'isopen',
        POSITION: 'position',
    };

    _private.showAppPreview = function() {
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_SHOW).addClass('hide');
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_HIDE).removeClass('hide');
    };
    _private.hideAppPreview = function() {
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_SHOW).removeClass('hide');
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_HIDE).addClass('hide');
    };

    _private.navigateBack = function() {
        _private.triggerPreviewEvent('back');
    };

    _private.refresh = function() {
        _private.triggerPreviewEvent('refresh');
    };

    _private.triggerPreviewEvent = function(action) {
        var $appPreviewIframe = $(module.SELECTORS.PREVIEW_WINDOW_IFRAME),
            previewWindow = $appPreviewIframe[0].contentWindow;
        previewWindow.postMessage({
            action: action,
        }, window.location.origin);
    };

    _private.toggleTabletView = function() {
        var $appPreview = $(module.SELECTORS.PREVIEW_WINDOW);
        if ($appPreview.hasClass('preview-tablet-mode')) {
            $appPreview.removeClass('preview-tablet-mode');
            _private.triggerPreviewEvent('phone-view');
        } else {
            $appPreview.addClass('preview-tablet-mode');
            _private.triggerPreviewEvent('tablet-view');
        }
    };

    _private.toggleAppPreview = function (e) {
        e.preventDefault();
        if (localStorage.getItem(module.DATA.OPEN) === module.DATA.OPEN) {
            localStorage.removeItem(module.DATA.OPEN);
        } else {
            localStorage.setItem(module.DATA.OPEN, module.DATA.OPEN);
        }
        $(window).trigger(module.EVENTS.RESIZE);
        if (localStorage.getItem(module.DATA.OPEN)) {
            _private.showAppPreview();
        } else {
            _private.hideAppPreview();
        }
    };

    module.initPreviewWindow = function (layoutController) {

        var $appPreview = $(module.SELECTORS.PREVIEW_WINDOW),
            $appBody = $(module.SELECTORS.APP_MANAGER_BODY),
            $togglePreviewBtn = $(module.SELECTORS.BTN_TOGGLE_PREVIEW),
            $messages = $(layoutController.selector.messages);

        $appPreview.data(module.DATA.POSITION, module.POSITION.FIXED);

        if (localStorage.getItem(module.DATA.OPEN)) {
            _private.showAppPreview();
        } else {
            _private.hideAppPreview();
        }

        $togglePreviewBtn.click(_private.toggleAppPreview);

        var _resizeAppPreview = function () {
            $appPreview.height($(window).outerHeight() + 'px');

            if (localStorage.getItem(module.DATA.OPEN)) {
                $appPreview.addClass('open');
                if ($('#formdesigner').length === 0) $appBody.addClass('offset-for-preview');
                $messages.addClass('offset-for-preview');
            } else {
                $appPreview.removeClass('open');
                if ($('#formdesigner').length === 0) $appBody.removeClass('offset-for-preview');
                $messages.removeClass('offset-for-preview');
            }

            var $nav = $(layoutController.selector.navigation);

            var maxHeight = $appPreview.find('.preview-phone-container').outerHeight() + $nav.outerHeight() + 80;
            if (($(window).height() <  maxHeight
                && $appPreview.data(module.DATA.POSITION) === module.POSITION.FIXED)
            ) {
                $appPreview.data(module.DATA.POSITION, module.POSITION.ABSOLUTE);
                $appPreview.addClass('small-height');
            } else if ($(window).height() >=  maxHeight
                && $appPreview.data(module.DATA.POSITION) === module.POSITION.ABSOLUTE) {
                $appPreview.data(module.DATA.POSITION, module.POSITION.FIXED);
                $appPreview.removeClass('small-height');
            }

            $(module.SELECTORS.BTN_TOGGLE_PREVIEW).fadeIn(500);

        };
        $(window).on(module.EVENTS.RESIZE, _resizeAppPreview);
        layoutController.utils.setBalancePreviewFn(_resizeAppPreview);
        $('.js-preview-toggle-tablet-view').click(_private.toggleTabletView);
        $('.js-preview-back').click(_private.triggerPreviewEvent.bind(this, 'back'));
        $('.js-preview-refresh').click(function() {
            $(module.SELECTORS.BTN_REFRESH).removeClass('app-out-of-date');
            _private.triggerPreviewEvent('refresh');
        });
        $(document).ajaxComplete(function(e, xhr, options) {
            if (/edit_form_attr/.test(options.url) ||
                /edit_module_attr/.test(options.url) ||
                /patch_xform/.test(options.url)) {
                $(module.SELECTORS.BTN_REFRESH).addClass('app-out-of-date');
            }
        });

    };

    module.prependToggleTo = function (selector, layout, attempts) {
        attempts = attempts || 0;
        if ($(selector).length) {
            var $toggleParent = $(selector);
            $toggleParent.prepend(layout);
            $toggleParent.find(module.SELECTORS.BTN_TOGGLE_PREVIEW).click(_private.toggleAppPreview);
            if (localStorage.getItem(module.DATA.OPEN)) {
                _private.showAppPreview();
            } else {
                _private.hideAppPreview();
            }
        } else if (attempts <= 30) {
            // give up appending element after waiting 30 seconds to load
            setTimeout(function () {
                module.prependToggleTo(selector, layout, attempts++);
            }, 1000);
        }
    };

    return module;
});
