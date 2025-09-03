from django.conf import settings

from corehq.apps.users.views import get_domain_languages


def get_languages_for_user(user):
    """
    Returns all CommCare supported languages and any languages that have
    explicitly been added to domains this user is a member of as a list
    of tuples list((language code, display name))
    """
    translated_languages = get_translated_languages()
    domain_languages = []
    for domain_membership in user.domain_memberships:
        domain_languages.extend(get_domain_languages(domain_membership.domain))

    # ensure only one language for each code is returned, giving precedent to translated_languages
    deduped_languages = {code: name for code, name in (domain_languages + translated_languages)}
    return sorted(list(deduped_languages.items()))


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
