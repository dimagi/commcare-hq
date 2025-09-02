from django.conf import settings


def get_translated_languages():
    """
    Returns list of tuples, (language code, display name) for all languages
    with translations supported by CommCare
    """
    languages = []
    for code, name in settings.LANGUAGES:
        display_name = format_language_for_display(code, name)
        languages.append((code, display_name))
    return languages


def format_language_for_display(code, name):
    return f"{code} ({name})"
