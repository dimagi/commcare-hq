# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import copy
import six
import re
from collections import defaultdict, namedtuple

from django.contrib import messages
from django.utils.translation import ugettext as _
from lxml import etree
from lxml.etree import XMLSyntaxError, Element

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.models import ShadowForm
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import namespaces, WrappedNode
from corehq.apps.translations.app_translations.utils import get_unicode_dicts
from corehq.apps.translations.exceptions import BulkAppTranslationsException


MarkdownStats = namedtuple('MarkdownStats', ['markdowns', 'vetoes'])


def update_app_from_form_sheet(app, rows, identifier):
    """
    Modify the translations of a form given a sheet of translation data.
    This does not save the changes to the DB.

    :param app:
    :param rows: Iterable of rows from a WorksheetJSONReader
    :param identifier: String like "menu1_form2"
    :return:  Returns a list of message tuples. The first item in each tuple is
    a function like django.contrib.messages.error, and the second is a string.
    """
    form = _get_form_from_sheet_name(app, identifier)
    rows = get_unicode_dicts(rows)

    try:
        _check_for_shadow_form_error(form)
    except BulkAppTranslationsException as e:
        return [(messages.error, six.text_type(e))]

    if form.source:
        xform = form.wrapped_xform()
    else:
        # This form is empty. Ignore it.
        return []

    try:
        itext = xform.itext_node
    except XFormException:
        # Can't do anything with this form. Ignore it.
        return []

    template_translation_el = _get_template_translation_el(app, itext)
    _add_missing_translation_elements_to_itext(app, template_translation_el, itext)
    markdown_stats = _get_markdown_stats(app, rows, itext)

    msgs = []
    (label_ids_to_skip, errors) = _get_label_ids_to_skip(form, rows)
    for error in errors:
        msgs.append((messages.error, error))

    # Update the translations
    for lang in app.langs:
        translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
        assert(translation_node.exists())

        for row in rows:
            if row['label'] in label_ids_to_skip:
                continue
            try:
                _add_or_remove_translations(app, lang, row, itext, markdown_stats)
            except BulkAppTranslationsException as e:
                msgs.append((messages.warning, six.text_type(e)))

    save_xform(app, form, etree.tostring(xform.xml))

    msgs = [(t, _('Error in {identifier}: ').format(identifier=identifier) + m) for (t, m) in msgs]
    return msgs


def _get_template_translation_el(app, itext):
    # Make language nodes for each language if they don't yet exist
    #
    # Currently operating under the assumption that every xForm has at least
    # one translation element, that each translation element has a text node
    # for each question and that each text node has a value node under it
    template_translation_el = None
    # Get a translation element to be used as a template for new elements
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if trans_el.exists():
            template_translation_el = trans_el
    assert(template_translation_el is not None)
    return template_translation_el


def _add_missing_translation_elements_to_itext(app, template_translation_el, itext):
    for lang in app.langs:
        trans_el = itext.find("./{f}translation[@lang='%s']" % lang)
        if not trans_el.exists():
            new_trans_el = copy.deepcopy(template_translation_el.xml)
            new_trans_el.set('lang', lang)
            if lang != app.langs[0]:
                # If the language isn't the default language
                new_trans_el.attrib.pop('default', None)
            else:
                new_trans_el.set('default', '')
            itext.xml.append(new_trans_el)


def _get_markdown_stats(app, rows, itext):
    # Aggregate Markdown vetoes, and translations that currently have Markdown
    vetoes = defaultdict(lambda: False)  # By default, Markdown is not vetoed for a label
    markdowns = defaultdict(lambda: False)  # By default, Markdown is not in use
    for lang in app.langs:
        # If Markdown is vetoed for one language, we apply that veto to other languages too. i.e. If a user has
        # told HQ that "**stars**" in an app's English translation is not Markdown, then we must assume that
        # "**étoiles**" in the French translation is not Markdown either.
        for row in rows:
            label_id = row['label']
            text_node = itext.find("./{f}translation[@lang='%s']/{f}text[@id='%s']" % (lang, label_id))
            vetoes[label_id] = vetoes[label_id] or _is_markdown_vetoed(text_node)
            markdowns[label_id] = markdowns[label_id] or _had_markdown(text_node)
    return MarkdownStats(markdowns=markdowns, vetoes=vetoes)


# skip labels that have no translation provided
def _get_label_ids_to_skip(form, rows):
    label_ids_to_skip = set()
    errors = []
    if form.is_registration_form():
        app = form.get_app()
        for row in rows:
            if not _has_translation(row, app.langs):
                label_ids_to_skip.add(row['label'])
        for label in label_ids_to_skip:
            errors.append(_("You must provide at least one translation for the label '%s'.") % (label))
    return (label_ids_to_skip, errors)


def _get_text_node(translation_node, label_id):
    text_node = translation_node.find("./{f}text[@id='%s']" % label_id)
    if text_node.exists():
        return text_node
    raise BulkAppTranslationsException(_("Unrecognized translation label {0}. "
                                         "That row has been skipped").format(label_id))


def _add_or_remove_translations(app, lang, row, itext, markdown_stats):
    label_id = row['label']
    translations = _get_translations_for_row(row, lang)
    translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
    keep_value_node = any(v for k, v in translations.items())
    text_node = _get_text_node(translation_node, label_id)
    for trans_type, new_translation in translations.items():
        if not new_translation:
            # If the cell corresponding to the label for this question
            # in this language is empty, fall back to another language
            for l in app.langs:
                key = _get_col_key(trans_type, l)
                if key not in row:
                    continue
                fallback = row[key]
                if fallback:
                    new_translation = fallback
                    break

        if trans_type == 'default':
            # plaintext/Markdown
            markdown_allowed = not markdown_stats.vetoes[label_id] or markdown_stats.markdowns[label_id]
            if _looks_like_markdown(new_translation) and markdown_allowed:
                # If it looks like Markdown, add it ... unless it
                # looked like Markdown before but it wasn't. If we
                # have a Markdown node, always keep it. FB 183536
                _update_translation_node(
                    new_translation,
                    text_node,
                    _get_markdown_node(text_node),
                    {'form': 'markdown'},
                    # If all translations have been deleted, allow the
                    # Markdown node to be deleted just as we delete
                    # the plaintext node
                    delete_node=(not keep_value_node)
                )
            _update_translation_node(
                new_translation,
                text_node,
                _get_value_node(text_node),
                {'form': 'default'},
                delete_node=(not keep_value_node)
            )
        else:
            # audio/video/image
            _update_translation_node(new_translation,
                                     text_node,
                                     text_node.find("./{f}value[@form='%s']" % trans_type),
                                     {'form': trans_type})


def _get_translations_for_row(row, lang):
    translations = dict()
    for trans_type in ['default', 'image', 'audio', 'video']:
        try:
            col_key = _get_col_key(trans_type, lang)
            translations[trans_type] = row[col_key]
        except KeyError:
            # has already been logged as unrecognized column
            pass
    return translations


def _update_translation_node(new_translation, text_node, value_node, attributes=None, delete_node=True):
    if delete_node and not new_translation:
        # Remove the node if it already exists
        if value_node.exists():
            value_node.xml.getparent().remove(value_node.xml)
        return

    # Create the node if it does not already exist
    if not value_node.exists():
        e = etree.Element(
            "{f}value".format(**namespaces), attributes
        )
        text_node.xml.append(e)
        value_node = WrappedNode(e)

    # Update the translation
    value_node.xml.tail = ''
    for node in value_node.findall("./*"):
        node.xml.getparent().remove(node.xml)
    escaped_trans = escape_output_value(new_translation)
    value_node.xml.text = escaped_trans.text
    for n in escaped_trans.getchildren():
        value_node.xml.append(n)


def _looks_like_markdown(str):
    return re.search(r'^\d+[\.\)] |^\*|~~.+~~|# |\*{1,3}\S+\*{1,3}|\[.+\]\(\S+\)', str, re.M)


def _get_markdown_node(text_node_):
    return text_node_.find("./{f}value[@form='markdown']")


def _get_value_node(text_node_):
    try:
        return next(
            n for n in text_node_.findall("./{f}value")
            if 'form' not in n.attrib or n.get('form') == 'default'
        )
    except StopIteration:
        return WrappedNode(None)


def _had_markdown(text_node_):
    """
    Returns True if a Markdown node currently exists for a translation.
    """
    markdown_node_ = _get_markdown_node(text_node_)
    return markdown_node_.exists()


def _is_markdown_vetoed(text_node_):
    """
    Return True if the value looks like Markdown but there is no
    Markdown node. It means the user has explicitly told form
    builder that the value isn't Markdown.
    """
    value_node_ = _get_value_node(text_node_)
    if not value_node_.exists():
        return False
    old_trans = etree.tostring(value_node_.xml, method="text", encoding="unicode").strip()
    return _looks_like_markdown(old_trans) and not _had_markdown(text_node_)


def _has_translation(row_, langs):
    for lang_ in langs:
        for trans_type_ in ['default', 'image', 'audio', 'video']:
            if row_.get(_get_col_key(trans_type_, lang_)):
                return True


def _get_form_from_sheet_name(app, sheet_name):
    mod_text, form_text = sheet_name.split("_")
    module_index = int(mod_text.replace("menu", "").replace("module", "")) - 1
    form_index = int(form_text.replace("form", "")) - 1
    return app.get_module(module_index).get_form(form_index)


def _check_for_shadow_form_error(form):
    if isinstance(form, ShadowForm):
        raise BulkAppTranslationsException(_('Form {index}, "{name}", is a shadow form. '
                 'Cannot translate shadow forms, skipping.').format(index=form.id + 1, name=form.default_name()))


def escape_output_value(value):
    try:
        return etree.fromstring("<value>{}</value>".format(
            re.sub(r"(?<!/)>", "&gt;", re.sub(r"<(\s*)(?!output)", "&lt;\\1", value))
        ))
    except XMLSyntaxError:
        # if something went horribly wrong just don't bother with escaping
        element = Element('value')
        element.text = value
        return element


def _get_col_key(translation_type, language):
    """
    Returns the name of the column in the bulk app translation spreadsheet
    given the translation type and language
    :param translation_type: What is being translated, i.e. 'default'
    or 'image'
    :param language:
    :return:
    """
    return "%s_%s" % (translation_type, language)
