from django.utils.translation import gettext_lazy


class BulkEditSessionType:
    CASE = 'case'
    FORM = 'form'
    CHOICES = (
        (CASE, 'Case'),
        (FORM, 'Form'),
    )


class PinnedFilterType:
    CASE_OWNERS = 'case_owners'
    CASE_STATUS = 'case_status'

    CHOICES = (
        (CASE_OWNERS, CASE_OWNERS),
        (CASE_STATUS, CASE_STATUS),
    )

    DEFAULT_FOR_CASE = (CASE_OWNERS, CASE_STATUS)


class DataType:
    TEXT = 'text'
    INTEGER = 'integer'
    PHONE_NUMBER = 'phone_number'
    DECIMAL = 'decimal'
    DATE = 'date'
    TIME = 'time'
    DATETIME = 'datetime'
    SINGLE_OPTION = 'single_option'
    MULTIPLE_OPTION = 'multiple_option'
    GPS = 'gps'
    BARCODE = 'barcode'
    PASSWORD = 'password'

    CHOICES = (
        (TEXT, TEXT),
        (INTEGER, INTEGER),
        (PHONE_NUMBER, PHONE_NUMBER),
        (DECIMAL, DECIMAL),
        (DATE, DATE),
        (TIME, TIME),
        (DATETIME, DATETIME),
        (SINGLE_OPTION, SINGLE_OPTION),
        (MULTIPLE_OPTION, MULTIPLE_OPTION),
        (GPS, GPS),
        (BARCODE, BARCODE),
        (PASSWORD, PASSWORD),
    )

    FORM_CHOICES = (
        (TEXT, gettext_lazy('Text')),
        (INTEGER, gettext_lazy('Integer')),
        (DECIMAL, gettext_lazy('Decimal')),
        (PHONE_NUMBER, gettext_lazy('Phone Number or Numeric ID')),
        (DATE, gettext_lazy('Date')),
        (TIME, gettext_lazy('Time')),
        (DATETIME, gettext_lazy('Date and Time')),
        (SINGLE_OPTION, gettext_lazy('Single Option')),
        (MULTIPLE_OPTION, gettext_lazy('Multiple Option')),
        (GPS, gettext_lazy('GPS')),
        (BARCODE, gettext_lazy('Barcode')),
        (PASSWORD, gettext_lazy('Password')),
    )

    CASE_CHOICES = (
        (TEXT, gettext_lazy('Text')),
        (INTEGER, gettext_lazy('Number')),
        (DATE, gettext_lazy('Date')),
        (DATETIME, gettext_lazy('Date and Time')),
        (MULTIPLE_OPTION, gettext_lazy('Multiple Choice')),
        (BARCODE, gettext_lazy('Barcode')),
        (GPS, gettext_lazy('GPS')),
        (PHONE_NUMBER, gettext_lazy('Phone Number or Numeric ID')),
        (PASSWORD, gettext_lazy('Password')),
    )

    FILTER_CATEGORY_TEXT = 'filter_text'
    FILTER_CATEGORY_NUMBER = 'filter_number'
    FILTER_CATEGORY_DATE = 'filter_date'
    FILTER_CATEGORY_MULTI_SELECT = 'filter_multi_select'

    FILTER_CATEGORY_DATA_TYPES = {
        FILTER_CATEGORY_TEXT: (
            TEXT,
            PHONE_NUMBER,
            BARCODE,
            PASSWORD,
            GPS,
            SINGLE_OPTION,
            TIME,
        ),
        FILTER_CATEGORY_NUMBER: (
            INTEGER,
            DECIMAL,
        ),
        FILTER_CATEGORY_DATE: (
            DATE,
            DATETIME,
        ),
        FILTER_CATEGORY_MULTI_SELECT: (MULTIPLE_OPTION,),
    }

    ICON_CLASSES = {
        TEXT: 'fcc fcc-fd-text',
        INTEGER: 'fcc fcc-fd-numeric',
        PHONE_NUMBER: 'fa fa-signal',
        DECIMAL: 'fcc fcc-fd-decimal',
        DATE: 'fa-solid fa-calendar-days',
        TIME: 'fa-regular fa-clock',
        DATETIME: 'fcc fcc-fd-datetime',
        SINGLE_OPTION: 'fcc fcc-fd-single-select',
        MULTIPLE_OPTION: 'fcc fcc-fd-multi-select',
        GPS: 'fa-solid fa-location-dot',
        BARCODE: 'fa fa-barcode',
        PASSWORD: 'fa fa-key',
    }

    @classmethod
    def get_filter_category(cls, data_type):
        for category, valid_data_types in cls.FILTER_CATEGORY_DATA_TYPES.items():
            if data_type in valid_data_types:
                return category


class FilterMatchType:
    EXACT = 'exact'
    IS_NOT = 'is_not'

    STARTS = 'starts'
    STARTS_NOT = 'starts_not'

    IS_EMPTY = 'is_empty'  # empty string
    IS_NOT_EMPTY = 'is_not_empty'

    IS_MISSING = 'missing'  # un-set
    IS_NOT_MISSING = 'not_missing'

    FUZZY = 'fuzzy'  # will use fuzzy-match from CQL
    FUZZY_NOT = 'not_fuzzy'  # will use not(fuzzy-match()) from CQL

    PHONETIC = 'phonetic'  # will use phonetic-match from CQL
    PHONETIC_NOT = 'not_phonetic'  # will use not(phonetic-match()) from CQL

    LESS_THAN = 'lt'
    GREATER_THAN = 'gt'

    LESS_THAN_EQUAL = 'lte'
    GREATER_THAN_EQUAL = 'gte'

    IS_ANY = 'is_any'  # we will use selected-any from CQL
    IS_NOT_ANY = 'is_not_any'  # we will use not(selected-any()) from CQL

    IS_ALL = 'is_all'  # we will use selected-all from CQL
    IS_NOT_ALL = 'is_not_all'  # we will use not(selected-all()) from CQL

    ALL_CHOICES = (
        (EXACT, EXACT),
        (IS_NOT, IS_NOT),
        (STARTS, STARTS),
        (STARTS_NOT, STARTS_NOT),
        (IS_EMPTY, IS_EMPTY),
        (IS_NOT_EMPTY, IS_NOT_EMPTY),
        (IS_MISSING, IS_MISSING),
        (IS_NOT_MISSING, IS_NOT_MISSING),
        (FUZZY, FUZZY),
        (FUZZY_NOT, FUZZY_NOT),
        (PHONETIC, PHONETIC),
        (PHONETIC_NOT, PHONETIC_NOT),
        (LESS_THAN, LESS_THAN),
        (GREATER_THAN, GREATER_THAN),
        (LESS_THAN_EQUAL, LESS_THAN_EQUAL),
        (GREATER_THAN_EQUAL, GREATER_THAN_EQUAL),
        (IS_ANY, IS_ANY),
        (IS_NOT_ANY, IS_NOT_ANY),
        (IS_ALL, IS_ALL),
        (IS_NOT_ALL, IS_NOT_ALL),
    )

    # choices valid for all data types
    ALL_DATA_TYPES_CHOICES = (
        (IS_EMPTY, gettext_lazy('is empty')),
        (IS_NOT_EMPTY, gettext_lazy('is not empty')),
        (IS_MISSING, gettext_lazy('is missing')),
        (IS_NOT_MISSING, gettext_lazy('is not missing')),
    )

    TEXT_CHOICES = (
        (EXACT, gettext_lazy('is exactly')),
        (IS_NOT, gettext_lazy('is not')),
        (STARTS, gettext_lazy('starts with')),
        (STARTS_NOT, gettext_lazy('does not start with')),
        (FUZZY, gettext_lazy('is like')),
        (FUZZY_NOT, gettext_lazy('is not like')),
        (PHONETIC, gettext_lazy('sounds like')),
        (PHONETIC_NOT, gettext_lazy('does not sound like')),
    )

    MULTI_SELECT_CHOICES = (
        (IS_ANY, gettext_lazy('is any')),
        (IS_NOT_ANY, gettext_lazy('is not any')),
        (IS_ALL, gettext_lazy('is all')),
        (IS_NOT_ALL, gettext_lazy('is not all')),
    )

    NUMBER_CHOICES = (
        (EXACT, gettext_lazy('equals')),
        (IS_NOT, gettext_lazy('does not equal')),
        (LESS_THAN, gettext_lazy('less than')),
        (LESS_THAN_EQUAL, gettext_lazy('less than or equal to')),
        (GREATER_THAN, gettext_lazy('greater than')),
        (GREATER_THAN_EQUAL, gettext_lazy('greater than or equal to')),
    )

    DATE_CHOICES = (
        (EXACT, gettext_lazy('on')),
        (LESS_THAN, gettext_lazy('before')),
        (LESS_THAN_EQUAL, gettext_lazy('before or on')),
        (GREATER_THAN, gettext_lazy('after')),
        (GREATER_THAN_EQUAL, gettext_lazy('on or after')),
    )


class EditActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'
    COPY_REPLACE = 'copy_replace'
    TITLE_CASE = 'title_case'
    UPPER_CASE = 'upper_case'
    LOWER_CASE = 'lower_case'
    MAKE_EMPTY = 'make_empty'
    MAKE_NULL = 'make_null'
    RESET = 'reset'

    DB_CHOICES = (
        (REPLACE, REPLACE),
        (FIND_REPLACE, FIND_REPLACE),
        (COPY_REPLACE, COPY_REPLACE),
        (STRIP, STRIP),
        (TITLE_CASE, TITLE_CASE),
        (UPPER_CASE, UPPER_CASE),
        (LOWER_CASE, LOWER_CASE),
        (MAKE_EMPTY, MAKE_EMPTY),
        (MAKE_NULL, MAKE_NULL),
        (RESET, RESET),
    )

    CHOICES = (
        (REPLACE, gettext_lazy('Replace')),
        (FIND_REPLACE, gettext_lazy('Find & Replace')),
        (COPY_REPLACE, gettext_lazy('Copy & Replace')),
        (STRIP, gettext_lazy('Strip Whitespaces')),
        (TITLE_CASE, gettext_lazy('Make Title Case')),
        (UPPER_CASE, gettext_lazy('Make Upper Case')),
        (LOWER_CASE, gettext_lazy('Make Lower Case')),
        (MAKE_EMPTY, gettext_lazy('Make Value Empty')),
        (MAKE_NULL, gettext_lazy('Make Value NULL')),
        (RESET, gettext_lazy('Reset Changes')),
    )
