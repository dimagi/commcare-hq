hqDefine("cloudcare/js/form_entry/const", function () {
    return {
        GROUP_TYPE: 'sub-group',
        REPEAT_TYPE: 'repeat-juncture',
        QUESTION_TYPE: 'question',

        // Entry types
        STRING: 'str',
        INT: 'int',
        LONG_INT: 'longint',
        FLOAT: 'float',
        SELECT: 'select',
        MULTI_SELECT: 'multiselect',
        DATE: 'date',
        TIME: 'time',
        DATETIME: 'datetime',
        GEO: 'geo',
        INFO: 'info',
        BARCODE: 'barcode',

        // Appearance attributes
        NUMERIC: 'numeric',
        ADDRESS: 'address',
        MINIMAL: 'minimal',
        LABEL: 'label',
        LIST_NOLABEL: 'list-nolabel',
        COMBOBOX: 'combobox',
        COMBOBOX_MULTIWORD: 'multiword',
        COMBOBOX_FUZZY: 'fuzzy',
        COLLAPSIBLE: 'group-collapse',
        COLLAPSIBLE_OPEN: 'collapse-open',
        COLLAPSIBLE_CLOSED: 'collapse-closed',
        ETHIOPIAN: 'ethiopian',

        // Note it's important to differentiate these two
        NO_PENDING_ANSWER: undefined,
        NO_ANSWER: null,

        // UI
        LABEL_WIDTH: 'col-sm-4',
        LABEL_OFFSET: 'col-sm-offset-4',
        CONTROL_WIDTH: 'col-sm-8',
        BLOCK_NONE: 'block-none',
        BLOCK_SUBMIT: 'block-submit',
        BLOCK_ALL: 'block-all',

        // XForm Navigation
        QUESTIONS_FOR_INDEX: 'questions_for_index',
        NEXT_QUESTION: 'next_index',
        PREV_QUESTION: 'prev_index',

        // XForm Actions
        NEW_FORM: 'new-form',
        ANSWER: 'answer',
        CURRENT: 'current',
        EVALUATE_XPATH: 'evaluate-xpath',
        NEW_REPEAT: 'new-repeat',
        DELETE_REPEAT: 'delete-repeat',
        SET_LANG: 'set-lang',
        SUBMIT: 'submit-all',
        FORMATTED_QUESTIONS: 'formatted_questions',
        CHANGE_LANG: 'change_lang',
        CHANGE_LOCALE: 'change_locale',

        // Control values. See commcare/javarosa/src/main/java/org/javarosa/core/model/Constants.java
        CONTROL_UNTYPED: -1,
        CONTROL_INPUT: 1,
        CONTROL_SELECT_ONE: 2,
        CONTROL_SELECT_MULTI: 3,
        CONTROL_TEXTAREA: 4,
        CONTROL_SECRET: 5,
        CONTROL_RANGE: 6,
        CONTROL_UPLOAD: 7,
        CONTROL_SUBMIT: 8,
        CONTROL_TRIGGER: 9,
        CONTROL_IMAGE_CHOOSE: 10,
        CONTROL_LABEL: 11,
        CONTROL_AUDIO_CAPTURE: 12,
        CONTROL_VIDEO_CAPTURE: 13,

        //knockout timeouts
        KO_ENTRY_TIMEOUT: 500,

        INT_LENGTH_LIMIT: 10,
        INT_VALUE_LIMIT: Math.pow(2, 31) - 1,
        LONGINT_LENGTH_LIMIT: 15,
        LONGINT_VALUE_LIMIT: Math.pow(2, 63) - 1,
        FLOAT_LENGTH_LIMIT: 15,
        FLOAT_VALUE_LIMIT: +("9".repeat(14)),
    };
});
