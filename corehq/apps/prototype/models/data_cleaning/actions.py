from django.utils.translation import gettext_lazy


class CleaningActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'
    COPY_REPLACE = 'copy_replace'
    TITLE_CASE = 'title_case'
    UPPER_CASE = 'upper_case'
    LOWER_CASE = 'lower_case'
    MAKE_NULL = 'make_null'

    OPTIONS = (
        (REPLACE, gettext_lazy("Replace")),
        (FIND_REPLACE, gettext_lazy("Find & Replace")),
        (COPY_REPLACE, gettext_lazy("Copy & Replace")),
        (STRIP, gettext_lazy("Strip Whitespaces")),
        (TITLE_CASE, gettext_lazy("Make Title Case")),
        (UPPER_CASE, gettext_lazy("Make Upper Case")),
        (LOWER_CASE, gettext_lazy("Make Lower Case")),
        (MAKE_NULL, gettext_lazy("Make Value NULL")),
    )

    FIND_ACTIONS = (
        FIND_REPLACE,
    )
    REPLACE_ALL_ACTIONS = (
        REPLACE,
    )
    COPY_ACTIONS = (
        COPY_REPLACE,
    )
