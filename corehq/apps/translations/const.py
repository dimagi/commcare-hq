MODULES_AND_FORMS_SHEET_NAME = "Menus_and_forms"
SINGLE_SHEET_NAME = "application"
SINGLE_SHEET_STATIC_HEADERS = [
    'menu_or_form',
    'case_property',  # modules only
    'list_or_detail',  # modules only
    'label',  # forms only
]

MODE_FILL_MISSING = 'fill_missing'
MODE_RETRANSLATE = 'retranslate'
AI_TRANSLATION_CHUNK_SIZE = 100
# saves tried when applying a run: the first against the copy the run
# translated, the rest rebased onto a fresh copy after a conflict
AI_TRANSLATION_APPLY_ATTEMPTS = 3
