# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import copy
import six
import re
from collections import defaultdict

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
    # Add missing translation elements
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

    def _update_translation_node(new_translation, value_node, attributes=None, delete_node=True):
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

    def get_markdown_node(text_node_):
        return text_node_.find("./{f}value[@form='markdown']")

    def get_value_node(text_node_):
        try:
            return next(
                n for n in text_node_.findall("./{f}value")
                if 'form' not in n.attrib or n.get('form') == 'default'
            )
        except StopIteration:
            return WrappedNode(None)

    def had_markdown(text_node_):
        """
        Returns True if a Markdown node currently exists for a translation.
        """
        markdown_node_ = get_markdown_node(text_node_)
        return markdown_node_.exists()

    def is_markdown_vetoed(text_node_):
        """
        Return True if the value looks like Markdown but there is no
        Markdown node. It means the user has explicitly told form
        builder that the value isn't Markdown.
        """
        value_node_ = get_value_node(text_node_)
        if not value_node_.exists():
            return False
        old_trans = etree.tostring(value_node_.xml, method="text", encoding="unicode").strip()
        return _looks_like_markdown(old_trans) and not had_markdown(text_node_)

    def has_translation(row_, langs):
        for lang_ in langs:
            for trans_type_ in ['default', 'image', 'audio', 'video']:
                if row_.get(_get_col_key(trans_type_, lang_)):
                    return True

    # Aggregate Markdown vetoes, and translations that currently have Markdown
    msgs = []
    vetoes = defaultdict(lambda: False)  # By default, Markdown is not vetoed for a label
    markdowns = defaultdict(lambda: False)  # By default, Markdown is not in use
    for lang in app.langs:
        # If Markdown is vetoed for one language, we apply that veto to other languages too. i.e. If a user has
        # told HQ that "**stars**" in an app's English translation is not Markdown, then we must assume that
        # "**étoiles**" in the French translation is not Markdown either.
        for row in rows:
            label_id = row['label']
            text_node = itext.find("./{f}translation[@lang='%s']/{f}text[@id='%s']" % (lang, label_id))
            vetoes[label_id] = vetoes[label_id] or is_markdown_vetoed(text_node)
            markdowns[label_id] = markdowns[label_id] or had_markdown(text_node)
    # skip labels that have no translation provided
    skip_label = set()
    if form.is_registration_form():
        for row in rows:
            if not has_translation(row, app.langs):
                skip_label.add(row['label'])
        for label in skip_label:
            msgs.append((
                messages.error,
                _("You must provide at least one translation"
                  " for the label '%s' in form %s") % (label, form.id + 1)
            ))

    # Update the translations
    for lang in app.langs:
        translation_node = itext.find("./{f}translation[@lang='%s']" % lang)
        assert(translation_node.exists())

        for row in rows:
            label_id = row['label']
            if label_id in skip_label:
                continue
            text_node = translation_node.find("./{f}text[@id='%s']" % label_id)
            if not text_node.exists():
                msgs.append((
                    messages.warning,
                    _("Unrecognized translation label {0} in form {1}. That row"
                      " has been skipped").format(label_id, form.id + 1)
                ))
                continue

            translations = dict()
            for trans_type in ['default', 'image', 'audio', 'video']:
                try:
                    col_key = _get_col_key(trans_type, lang)
                    translations[trans_type] = row[col_key]
                except KeyError:
                    # has already been logged as unrecoginzed column
                    continue

            keep_value_node = any(v for k, v in translations.items())

            # Add or remove translations
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
                    if _looks_like_markdown(new_translation) and not vetoes[label_id] or markdowns[label_id]:
                        # If it looks like Markdown, add it ... unless it
                        # looked like Markdown before but it wasn't. If we
                        # have a Markdown node, always keep it. FB 183536
                        _update_translation_node(
                            new_translation,
                            get_markdown_node(text_node),
                            {'form': 'markdown'},
                            # If all translations have been deleted, allow the
                            # Markdown node to be deleted just as we delete
                            # the plaintext node
                            delete_node=(not keep_value_node)
                        )
                    _update_translation_node(
                        new_translation,
                        get_value_node(text_node),
                        {'form': 'default'},
                        delete_node=(not keep_value_node)
                    )
                else:
                    # audio/video/image
                    _update_translation_node(new_translation,
                                             text_node.find("./{f}value[@form='%s']" % trans_type),
                                             {'form': trans_type})

    save_xform(app, form, etree.tostring(xform.xml))
    return msgs


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
            re.sub(r"(?<!/)>", "&gt;", re.sub("<(\s*)(?!output)", "&lt;\\1", value))
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
