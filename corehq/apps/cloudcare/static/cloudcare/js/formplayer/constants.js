hqDefine("cloudcare/js/formplayer/constants", function () {
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

        SMALL_SCREEN_WIDTH_PX: 768,
    };
});
