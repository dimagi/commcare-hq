from django.utils.translation import gettext_lazy


class CleaningActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'

    OPTIONS = (
        (REPLACE, gettext_lazy("Replace")),
        (FIND_REPLACE, gettext_lazy("Find & Replace")),
        (STRIP, gettext_lazy("Strip Whitespaces")),
    )

    FIND_ACTIONS = (
        FIND_REPLACE,
    )
    REPLACE_ALL_ACTIONS = (
        REPLACE,
    )
