'use strict';
hqDefine("cloudcare/js/formplayer/constants", [], function () {
    return {
        ALLOWED_SAVED_OPTIONS: ['oneQuestionPerScreen', 'language'],

        // These should match corehq/apps/cloudcare/const.py
        WEB_APPS_ENVIRONMENT: 'web-apps',
        PREVIEW_APP_ENVIRONMENT: 'preview-app',
        GENERIC_ERROR: gettext(
            'An unexpected error occurred. ' +
            'Please report an issue if you continue to see this message.'
        ),

        LayoutStyles: {
            GRID: 'grid',
            LIST: 'list',
        },
        ALLOWED_FIELD_ALIGNMENTS: ['start', 'end', 'center', 'left', 'right'],

        DEFAULT_INCOMPLETE_FORMS_PAGE_SIZE: 10,

        MULTI_SELECT_ADD: 'add',
        MULTI_SELECT_REMOVE: 'remove',
        MULTI_SELECT_MAX_SELECT_VALUE: 100,

        FORMAT_ADDRESS: "Address",
        FORMAT_ADDRESS_POPUP: "AddressPopup",
        FORMAT_CLICKABLE_ICON: "ClickableIcon",
        FORMAT_MARKDOWN: "Markdown",

        ENTITIES: "entities",
        QUERY: "query",

        // values are snake case as recommended for Datadog tags
        queryInitiatedBy: {
            DYNAMIC_SEARCH: 'dynamic_search',
            FIELD_CHANGE: "field_change",
        },

        //Custom Properties
        POST_FORM_SYNC: "cc-sync-after-form",

        SMALL_SCREEN_WIDTH_PX: 992,

        BREADCRUMB_HEIGHT_PX: 46.125,
        BREADCRUMB_WIDTH_OFFSET_PX: 120.41, // unavailable breadcrumb space i.e. padding, home and hamburger icons

        COLLAPSIBLE_TILE_MAX_HEIGHT: 150,
    };
});
