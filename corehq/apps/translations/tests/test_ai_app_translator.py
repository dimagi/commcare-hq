import pytest

from corehq.apps.translations.app_translations.ai_translator import (
    is_valid_app_translation,
)


@pytest.mark.parametrize("source, translated, valid", [
    ("Name", "Nom", True),
    ("Name", "", False),                      # empty output
    ("Name", None, False),                    # non-string output
    # <output> tags must survive verbatim (count + name sequence + attrs)
    ('Hello <output value="/data/name"/>', 'Bonjour <output value="/data/name"/>', True),
    ('Hello <output value="/data/name"/>', 'Bonjour', False),
    ('Hello <output value="/data/name"/>', 'Bonjour <output value="/data/nom"/>', False),
    # HTML tag sequence preserved
    ("<b>Save</b>", "<b>Enregistrer</b>", True),
    ("<b>Save</b>", "Enregistrer", False),
    # URLs preserved
    ("See https://example.com/help", "Voir https://example.com/help", True),
    ("See https://example.com/help", "Voir https://exemple.fr/aide", False),
    # %/{} have no runtime meaning in app content — free to change
    ("Hi {name}", "Salut {nom}", True),
    ("75% complete", "75 % terminé", True),
    # markdown renders on mobile: marker counts must survive
    ("**Warning** do not proceed", "**Attention** ne continuez pas", True),
    ("**Warning** do not proceed", "Attention ne continuez pas", False),
    # fill-in-the-blank runs may be resized but not dropped
    ("Name: ____", "Nom : ______", True),
    ("Name: ____", "Nom :", False),
    # list structure must keep the same number of items
    ("- Wash hands\n- Boil water", "- Lavez les mains\n- Faites bouillir l'eau", True),
    ("- Wash hands\n- Boil water", "Lavez les mains et faites bouillir l'eau", False),
    ("1. First\n2. Second", "1. Premier\n2. Deuxième", True),
    ("1. First\n2. Second", "Premier puis deuxième", False),
    # headings
    ("# Instructions", "# Instructions traduites", True),
    ("# Instructions", "Instructions traduites", False),
    # link syntax survives with the label translated
    ("See [help](https://example.com)", "Voir [aide](https://example.com)", True),
    ("See [help](https://example.com)", "Voir aide : https://example.com", False),
    # trailing punctuation swallowed by the URL regex must not fail it
    ("Go to (https://example.com/help)", "Aller à https://example.com/help !", True),
    # natural-language asterisks/hyphens that are not markdown never trip it
    ("Required *", "Requis", True),
    ("Follow-up visit", "Visite de suivi", True),
])
def test_is_valid_app_translation(source, translated, valid):
    assert is_valid_app_translation(source, translated) is valid
