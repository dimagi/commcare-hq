from django.utils.translation import gettext_lazy


class CleaningActionType:
    REPLACE = 'replace'
    FIND_REPLACE = 'find_replace'
    STRIP = 'strip'
    MERGE = 'merge'

    OPTIONS = (
        (REPLACE, gettext_lazy("Replace")),
        (FIND_REPLACE, gettext_lazy("Find & Replace")),
        (STRIP, gettext_lazy("Strip Whitespaces")),
        (MERGE, gettext_lazy("Merge")),
    )

    FIND_ACTIONS = (
        FIND_REPLACE,
    )
    REPLACE_ALL_ACTIONS = (
        REPLACE,
    )
    MERGE_ACTIONS = (
        MERGE,
    )
