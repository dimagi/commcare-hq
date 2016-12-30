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
        OFFSET_FOR_PREVIEW: '.offset-for-preview',
        FORMDESIGNER: '#formdesigner',
    };

    module.EVENTS = {
        RESIZE: 'previewApp.resize',
    };

    module.POSITION = {
        FIXED: 'fixed',
        ABSOLUTE: 'absolute',
    };

    module.DATA = {
        OPEN: 'preview-isopen',
        POSITION: 'position',
        TABLET: 'preview-tablet',
    };

    _private.isFormdesigner = false;

    _private.showAppPreview = function(triggerAnalytics) {
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_SHOW).addClass('hide');
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_HIDE).removeClass('hide');
        if (_private.isFormdesigner) {
            $(module.SELECTORS.FORMDESIGNER).addClass('offset-for-preview');
        }

        if (triggerAnalytics) {
            window.analytics.workflow("[app-preview] Clicked Show App Preview");
            window.analytics.usage("[app-preview] Clicked Show App Preview");
        }

    };
    _private.hideAppPreview = function(triggerAnalytics) {
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_SHOW).removeClass('hide');
        $(module.SELECTORS.PREVIEW_ACTION_TEXT_HIDE).addClass('hide');
        if (_private.isFormdesigner) {
            $(module.SELECTORS.FORMDESIGNER).removeClass('offset-for-preview');
        }

        if (triggerAnalytics) {
            window.analytics.workflow("[app-preview] Clicked Hide App Preview");
            window.analytics.usage("[app-preview] Clicked Hide App Preview");
        }
    };

    _private.tabletView = function(triggerAnalytics) {
        var $appPreview = $(module.SELECTORS.PREVIEW_WINDOW);
        $appPreview.addClass('preview-tablet-mode');
        $(module.SELECTORS.OFFSET_FOR_PREVIEW).addClass('offset-for-tablet');
        _private.triggerPreviewEvent('tablet-view');

        if (triggerAnalytics) {
            window.analytics.workflow('[app-preview] User turned on tablet mode');
        }
    };

    _private.phoneView = function(triggerAnalytics) {
        var $appPreview = $(module.SELECTORS.PREVIEW_WINDOW);
        $appPreview.removeClass('preview-tablet-mode');
        $(module.SELECTORS.OFFSET_FOR_PREVIEW).removeClass('offset-for-tablet');
        _private.triggerPreviewEvent('phone-view');

        if (triggerAnalytics) {
            window.analytics.workflow('[app-preview] User turned off tablet mode');
        }
    };

    _private.navigateBack = function() {
        _private.triggerPreviewEvent('back');
    };

    _private.triggerPreviewEvent = function(action) {
        var $appPreviewIframe = $(module.SELECTORS.PREVIEW_WINDOW_IFRAME),
            previewWindow = $appPreviewIframe[0].contentWindow;
        previewWindow.postMessage({
            action: action,
        }, window.location.origin);
    };

    _private.toggleTabletView = function() {
        _private.toggleLocalStorageDatum(module.DATA.TABLET);
        if (localStorage.getItem(module.DATA.TABLET)) {
            _private.tabletView(true);
        } else {
            _private.phoneView(true);
        }
    };

    _private.toggleLocalStorageDatum = function(datum) {
        if (localStorage.getItem(datum) === datum) {
            localStorage.removeItem(datum);
        } else {
            localStorage.setItem(datum, datum);
        }
    };

    _private.toggleAppPreview = function (e) {
        e.preventDefault();
        _private.toggleLocalStorageDatum(module.DATA.OPEN);
        $(window).trigger(module.EVENTS.RESIZE);
        if (localStorage.getItem(module.DATA.OPEN)) {
            _private.showAppPreview(true);
        } else {
            _private.hideAppPreview(true);
        }
    };

    module.initPreviewWindow = function (layoutController) {

        var $appPreview = $(module.SELECTORS.PREVIEW_WINDOW),
            $appBody = $(module.SELECTORS.APP_MANAGER_BODY),
            $togglePreviewBtn = $(module.SELECTORS.BTN_TOGGLE_PREVIEW),
            $messages = $(layoutController.selector.messages);

        _private.isFormdesigner = $(module.SELECTORS.FORMDESIGNER).length > 0;

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
                if (!_private.isFormdesigner) $appBody.addClass('offset-for-preview');
                $messages.addClass('offset-for-preview');
            } else {
                $appPreview.removeClass('open');
                if (!_private.isFormdesigner) $appBody.removeClass('offset-for-preview');
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
            window.analytics.workflow("[app-preview] Clicked Refresh App Preview");
            window.analytics.usage("[app-preview] Clicked Refresh App Preview");
        });
        $(document).ajaxComplete(function(e, xhr, options) {
            if (/edit_form_attr/.test(options.url) ||
                /edit_module_attr/.test(options.url) ||
                /edit_module_detail_screens/.test(options.url) ||
                /edit_app_attr/.test(options.url) ||
                /edit_form_actions/.test(options.url) ||
                /edit_commcare_settings/.test(options.url) ||
                /patch_xform/.test(options.url)) {
                $(module.SELECTORS.BTN_REFRESH).addClass('app-out-of-date');
            }
        });
        $(module.SELECTORS.PREVIEW_WINDOW_IFRAME).on('load', function() {
            if (localStorage.getItem(module.DATA.TABLET)) {
                _private.tabletView();
            } else {
                _private.phoneView();
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
