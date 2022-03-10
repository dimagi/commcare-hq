hqDefine("cloudcare/js/formplayer/constants", function () {
    return {
        ALLOWED_SAVED_OPTIONS: ['oneQuestionPerScreen', 'language'],

        // These should match corehq/apps/cloudcare/const.py
        WEB_APPS_ENVIRONMENT: 'web-apps',
        PREVIEW_APP_ENVIRONMENT: 'preview-app',
        GENERIC_ERROR: gettext(
            'Formplayer encountered an error. ' +
            'Please report an issue if you continue to see this message.'
        ),

        LayoutStyles: {
            GRID: 'grid',
            LIST: 'list',
        },
        DEFAULT_INCOMPLETE_FORMS_PAGE_SIZE: 20,
    };
});
