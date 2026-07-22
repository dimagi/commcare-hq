const PREVIEW_WINDOW = '#js-appmanager-preview';

export const SELECTORS = {
    BTN_TOGGLE_PREVIEW: '.js-preview-toggle',
    PREVIEW_WINDOW: PREVIEW_WINDOW,
    PREVIEW_WINDOW_IFRAME: `${PREVIEW_WINDOW} iframe`,
    APP_MANAGER_BODY: '#js-appmanager-body',
    PREVIEW_ACTION_TEXT_SHOW: '.js-preview-action-show',
    PREVIEW_ACTION_TEXT_HIDE: '.js-preview-action-hide',
    BTN_REFRESH: '.js-preview-refresh',
    OFFSET_FOR_PREVIEW: '.offset-for-preview',
    FORMDESIGNER: '#formdesigner',
};

export const EVENTS = {
    RESIZE: 'previewApp.resize',
};

export const POSITION = {
    FIXED: 'fixed',
    ABSOLUTE: 'absolute',
};

export const DATA = {
    OPEN: 'preview-isopen',
    POSITION: 'position',
    TABLET: 'preview-tablet',   // also referenced in cloudcare/js/preview_app/preview_app
};
