/* globals $ */
/* globals window */

hqDefine('app_manager/js/preview_app.js', function() {
    'use strict';
    var module = {};
    
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
    
    module.initPreviewWindow = function (
        previewWindowSelector,
        appManagerBodySelector,
        previewToggleBtnSelector
    ) {
        
        var $appPreview = $(previewWindowSelector);
        var $appBody = $(appManagerBodySelector);
        var $togglePreviewBtn = $(previewToggleBtnSelector);

        $appPreview.data(module.DATA.OPEN, false);
        $appPreview.data(module.DATA.POSITION, module.POSITION.FIXED);

        var _toggleAppPreview = function () {
            $appPreview.data(module.DATA.OPEN, !$appPreview.data(module.DATA.OPEN));
            $(window).trigger(module.EVENTS.RESIZE);
            if($appPreview.data(module.DATA.OPEN)) {
                $('.preview-action-show').addClass('hide');
                $('.preview-action-hide').removeClass('hide');
            } else {
                $('.preview-action-show').removeClass('hide');
                $('.preview-action-hide').addClass('hide');
            }
        };
        if ($togglePreviewBtn) {
            $togglePreviewBtn.click(_toggleAppPreview);
        }
        $appPreview.find('.btn-preview-close').click(_toggleAppPreview);

        var _resizeAppPreview = function (event) {
            if ($appPreview.data(module.DATA.OPEN)) {
                $appPreview.addClass('open');
                $appBody.css('margin-right', $appPreview.outerWidth() + 50 + 'px');
            } else {
                $appPreview.removeClass('open');
                $appBody.css('margin-right', 0);
            }
            var maxHeight = $appPreview.outerHeight() + 120;
            if ($(window).height() <  maxHeight
                && $appPreview.data(module.DATA.POSITION) === module.POSITION.FIXED) {
                $appPreview.data(module.DATA.POSITION, module.POSITION.ABSOLUTE);
                $appPreview.addClass('small-height');
            } else if ($(window).height() >=  maxHeight
                && $appPreview.data(module.DATA.POSITION) === module.POSITION.ABSOLUTE) {
                $appPreview.data(module.DATA.POSITION, module.POSITION.FIXED);
                $appPreview.removeClass('small-height');
            }
        };
        _resizeAppPreview();
        $(window).resize(_resizeAppPreview);
        $(window).on(module.EVENTS.RESIZE, _resizeAppPreview);

    };

    return module;
});
