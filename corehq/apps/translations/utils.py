from __future__ import absolute_import
from __future__ import unicode_literals

import tempfile

import six

from corehq.apps.app_manager.models import LinkedApplication
from corehq import toggles


def get_file_content_from_workbook(wb):
    # temporary write the in-memory workbook to be able to read its content
    with tempfile.TemporaryFile(suffix='.xlsx') as f:
        wb.save(f)
        f.seek(0)
        content = f.read()
    return content


def update_app_translations_from_trans_dict(app, trans_dict):
    if toggles.PARTIAL_UI_TRANSLATIONS.enabled(app.domain):
        if isinstance(app, LinkedApplication):
            for lang, trans in six.iteritems(app.translations):
                if lang in trans_dict:
                    app.translations[lang].update(trans_dict[lang])

        for lang, trans in six.iteritems(app.translations):
            if lang in trans_dict:
                app.translations[lang].update(trans_dict[lang])
    else:
        if isinstance(app, LinkedApplication):
            app.linked_app_translations.update(trans_dict)
        app.translations.update(trans_dict)


def zip_with_gaps(all_items, some_items, allitem_keyfunc=None, someitem_keyfunc=None):
    """
    Yields pairs of items from `all_items` and `some_items` where item
    keys match.

    Keys do not need to be unique. Keys in `all_items` must be a
    superset of keys in `some_items`. If key functions are not given,
    the key is item[0].

    >>> long_list = ['Alice', 'Apple', 'Bengal', 'Carrot', 'Daring', 'Danger', 'Dakar', 'Electric']
    >>> short_list = ['Cabernet', 'Daedalus', 'Daimler', 'Dog']
    >>> list(zip_with_gaps(long_list, short_list)) == [
    ...    ('Carrot', 'Cabernet'), ('Daring', 'Daedalus'), ('Danger', 'Daimler'), ('Dakar', 'Dog')
    ... ]
    True

    """
    if allitem_keyfunc is None:
        allitem_keyfunc = lambda x: x[0]  # noqa: E731
    if someitem_keyfunc is None:
        someitem_keyfunc = lambda x: x[0]  # noqa: E731

    all_iterable = iter(all_items)
    for s_item in some_items:
        a_item = next(all_iterable)
        while someitem_keyfunc(s_item) != allitem_keyfunc(a_item):
            a_item = next(all_iterable)
        yield (a_item, s_item)
