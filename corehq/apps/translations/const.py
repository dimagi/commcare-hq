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
AI_TRANSLATION_APPLY_ATTEMPTS = 3

# Runs for one app execute one at a time. A queued run retries every
# RETRY_DELAY until the app's lock is free, giving up after MAX_RETRIES.
AI_TRANSLATION_RETRY_DELAY = 3 * 60
AI_TRANSLATION_MAX_RETRIES = 100
# Longest a run is expected to take; the app's lock expires after this
AI_TRANSLATION_LOCK_TIMEOUT = 30 * 60
