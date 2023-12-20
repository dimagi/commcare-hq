import copy
import re
from collections import defaultdict

from django.contrib import messages
from django.utils.translation import gettext as _

from lxml import etree
from lxml.etree import Element, XMLSyntaxError

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.models import ShadowForm
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import WrappedNode, namespaces
from corehq.apps.translations.app_translations.utils import (
    BulkAppTranslationUpdater,
    get_form_from_sheet_name,
    get_unicode_dicts,
)
from corehq.apps.translations.exceptions import BulkAppTranslationsException


class BulkAppTranslationFormUpdater(BulkAppTranslationUpdater):
    def __init__(self, app, sheet_name, unique_id=None, lang=None):
        '''
        :param sheet_name: String like "menu1_form2"
        '''
        super(BulkAppTranslationFormUpdater, self).__init__(app, lang)
        self.sheet_name = sheet_name

        # These attributes depend on each other and therefore need to be created in this order
        if unique_id:
            self.form = app.get_form(unique_id)
        else:
            self.form = get_form_from_sheet_name(self.app, sheet_name)
        self.xform = self._get_xform()
        self.itext = self._get_itext()

        # These attributes get populated by update
        self.markdowns = None
        self.markdown_vetoes = None

    def _get_xform(self):
        if not isinstance(self.form, ShadowForm) and self.form.source:
            return self.form.wrapped_xform()

    def _get_itext(self):
        """
        find the bucket node that holds all translations.
        it has a bunch of nodes, one for each lang, which then
        has translations for all labels as a child node, example
        <itext>
        <translation lang="en" default="">
         <text id="name-label">
           <value>Name2</value>
           <value form="image">image_path</value>
         </text>
        </translation>
        </itext>
        """
        if self.xform:
            try:
                return self.xform.itext_node
            except XFormException:
                # Should be a blank form with no questions added so far, shouldn't need any update so skip.
                pass

    def update(self, rows):
        try:
            self._check_for_shadow_form_error()
        except BulkAppTranslationsException as e:
            return [(messages.error, str(e))]

        if not self.itext:
            # This form is empty or malformed. Ignore it.
            return []

        # Setup
        rows = get_unicode_dicts(rows)
        template_translation_el = self._get_template_translation_el()
        self._add_missing_translation_elements_to_itext(template_translation_el)
        self._populate_markdown_stats(rows)
        self.msgs = []

        # Skip labels that have no translation provided
        label_ids_to_skip = self._get_label_ids_to_skip(rows)

        # Update the translations
        for lang in self.langs:
            translation_node = self.itext.find("./{f}translation[@lang='%s']" % lang)
            assert translation_node.exists()

            for row in rows:
                if row['label'] in label_ids_to_skip:
                    continue
                if row['label'] == 'submit_label':
                    try:
                        self.form.submit_label[lang] = row[self._get_col_key('default', lang)]
                    except KeyError:
                        pass
                    continue
                if row['label'] == 'submit_notification_label':
                    notification_value = ''
                    try:
                        notification_value = row[self._get_col_key('default', lang)]
                    except KeyError:
                        pass
                    if notification_value:
                        self.form.submit_notification_label[lang] = notification_value
                    continue
                try:
                    self._add_or_remove_translations(lang, row)
                except BulkAppTranslationsException as e:
                    self.msgs.append((messages.warning, str(e)))

        save_xform(self.app, self.form, etree.tostring(self.xform.xml, encoding='utf-8'))

        return [(t, _('Error in {sheet}: {msg}').format(sheet=self.sheet_name, msg=m)) for (t, m) in self.msgs]

    def _get_template_translation_el(self):
        # Make language nodes for each language if they don't yet exist
        #
        # Currently operating under the assumption that every xForm has at least
        # one translation element, that each translation element has a text node
        # for each question and that each text node has a value node under it.
        # Get a translation element to be used as a template for new elements, preferably of default lang
        default_lang = self.app.default_language
        default_trans_el = self.itext.find("./{f}translation[@lang='%s']" % default_lang)
        if default_trans_el.exists():
            return default_trans_el
        non_default_langs = copy.copy(self.app.langs)
        non_default_langs.remove(default_lang)
        for lang in non_default_langs:
            trans_el = self.itext.find("./{f}translation[@lang='%s']" % lang)
            if trans_el.exists():
                return trans_el
        raise Exception(_("Form has no translation node present to be used as a template."))

    def _add_missing_translation_elements_to_itext(self, template_translation_el):
        for lang in self.langs:
            trans_el = self.itext.find("./{f}translation[@lang='%s']" % lang)
            if not trans_el.exists():
                new_trans_el = copy.deepcopy(template_translation_el.xml)
                new_trans_el.set('lang', lang)
                if lang != self.app.langs[0]:
                    # If the language isn't the default language
                    new_trans_el.attrib.pop('default', None)
                else:
                    new_trans_el.set('default', '')
                self.itext.xml.append(new_trans_el)

    def _populate_markdown_stats(self, rows):
        # Aggregate Markdown vetoes, and translations that currently have Markdown
        self.markdowns = defaultdict(lambda: False)  # By default, Markdown is not in use
        self.markdown_vetoes = defaultdict(lambda: False)  # By default, Markdown is not vetoed for a label
        for lang in self.langs:
            # If Markdown is vetoed for one language, we apply that veto to other languages too. i.e. If a user has
            # told HQ that "**stars**" in an app's English translation is not Markdown, then we must assume that
            # "**étoiles**" in the French translation is not Markdown either.
            for row in rows:
                label_id = row['label']
                text_node = self.itext.find("./{f}translation[@lang='%s']/{f}text[@id='%s']" % (lang, label_id))
                if self._is_markdown_vetoed(text_node):
                    self.markdown_vetoes[label_id] = True
                self.markdowns[label_id] = self.markdowns[label_id] or self._had_markdown(text_node)

    def _get_label_ids_to_skip(self, rows):
        label_ids_to_skip = set()
        if self.form.is_registration_form():
            for row in rows:
                if not self._has_translation(row):
                    label_ids_to_skip.add(row['label'])
            for label in label_ids_to_skip:
                if label == 'submit_notification_label':
                    continue
                self.msgs.append((
                    messages.error,
                    _("You must provide at least one translation for the label '{}'.").format(label)))
        return label_ids_to_skip

    def _get_text_node(self, translation_node, label_id):
        text_node = translation_node.find("./{f}text[@id='%s']" % label_id)
        if text_node.exists():
            return text_node
        raise BulkAppTranslationsException(_("Unrecognized translation label {0}. "
                                             "That row has been skipped").format(label_id))

    def _add_or_remove_translations(self, lang, row):
        label_id = row['label']
        translations = self._get_translations_for_row(row, lang)
        translation_node = self.itext.find("./{f}translation[@lang='%s']" % lang)
        keep_value_node = not self.is_multi_sheet or any(v for k, v in translations.items())
        text_node = self._get_text_node(translation_node, label_id)
        for trans_type, new_translation in translations.items():
            if self.is_multi_sheet and not new_translation:
                # If the cell corresponding to the label for this question
                # in this language is empty, fall back to another language
                for language in self.langs:
                    key = self._get_col_key(trans_type, language)
                    if key not in row:
                        continue
                    fallback = row[key]
                    if fallback:
                        new_translation = fallback
                        break

            if trans_type == 'default':
                # Always update plain text
                self._update_translation_node(
                    new_translation,
                    text_node,
                    self._get_value_node(text_node),
                    delete_node=(not keep_value_node)
                )

                # Also update markdown if either of the following is true:
                # - The new translation uses markdown...unless the user has explicitly specified it is NOT markdown
                # - The question has used markdown in the past. If the markdown node exists, it needs to stay up to
                #   date, since mobile will display the markdown value if it's present.
                is_markdown = self._looks_like_markdown(new_translation) and not self.markdown_vetoes[label_id]
                if is_markdown or self.markdowns[label_id]:
                    # If it looks like Markdown, add it ... unless it
                    # looked like Markdown before but it wasn't. If we
                    # have a Markdown node, always keep it. FB 183536
                    self._update_translation_node(
                        new_translation,
                        text_node,
                        self._get_markdown_node(text_node),
                        {'form': 'markdown'},
                        # If all translations have been deleted, allow the
                        # Markdown node to be deleted just as we delete
                        # the plaintext node
                        delete_node=(not keep_value_node)
                    )
            else:
                # audio/video/image
                self._update_translation_node(new_translation,
                                              text_node,
                                              text_node.find("./{f}value[@form='%s']" % trans_type),
                                              {'form': trans_type})

    def _get_translations_for_row(self, row, lang):
        translations = dict()
        for trans_type in ['default', 'image', 'audio', 'video']:
            try:
                col_key = self._get_col_key(trans_type, lang)
                translations[trans_type] = row[col_key]
            except KeyError:
                # has already been logged as unrecognized column
                pass
        return translations

    def _update_translation_node(self, new_translation, text_node, value_node, attributes=None, delete_node=True):
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
        escaped_trans = self.escape_output_value(new_translation)
        value_node.xml.text = escaped_trans.text
        for n in escaped_trans:
            value_node.xml.append(n)

    def _looks_like_markdown(self, str):
        return re.search(r'^\d+[\.\)] |^\*|~~.+~~|# |\*{1,3}\S+\*{1,3}|\[.+\]\(\S+\)', str, re.M)

    def _get_markdown_node(self, text_node_):
        return text_node_.find("./{f}value[@form='markdown']")

    @staticmethod
    def _get_default_value_nodes(text_node_):
        for value_node in text_node_.findall("./{f}value"):
            if 'form' not in value_node.attrib:
                yield value_node
            elif value_node.get('form') == 'default':
                # migrate invalid values, http://manage.dimagi.com/default.asp?236239#BugEvent.1214824
                value_node.attrib.pop('form')
                yield value_node

    def _get_value_node(self, text_node_):
        default_value_nodes = list(self._get_default_value_nodes(text_node_))
        if len(default_value_nodes) > 1:
            raise XFormException(_("Found conflicting nodes for label {}").format(text_node_.get('id')))
        if default_value_nodes:
            return default_value_nodes[0]
        return WrappedNode(None)

    def _had_markdown(self, text_node_):
        """
        Returns True if a Markdown node currently exists for a translation.
        """
        markdown_node_ = self._get_markdown_node(text_node_)
        return markdown_node_.exists()

    def _is_markdown_vetoed(self, text_node_):
        """
        Return True if the value looks like Markdown but there is no
        Markdown node. It means the user has explicitly told form
        builder that the value isn't Markdown.
        """
        value_node_ = self._get_value_node(text_node_)
        if not value_node_.exists():
            return False
        old_trans = etree.tostring(
            value_node_.xml, method="text", encoding='utf-8'
        ).decode('utf-8').strip()
        return self._looks_like_markdown(old_trans) and not self._had_markdown(text_node_)

    def _has_translation(self, row):
        for lang_ in self.langs:
            for trans_type_ in ['default', 'image', 'audio', 'video']:
                if row.get(self._get_col_key(trans_type_, lang_)):
                    return True

    def _check_for_shadow_form_error(self):
        if isinstance(self.form, ShadowForm):
            raise BulkAppTranslationsException(_('Form {index}, "{name}", is a shadow form. '
                     'Cannot translate shadow forms, skipping.').format(index=self.form.id + 1,
                                                                        name=self.form.default_name()))

    @classmethod
    def escape_output_value(cls, value):
        try:
            return etree.fromstring("<value>{}</value>".format(
                re.sub(r"(?<!/)>", "&gt;", re.sub(r"<(\s*)(?!output)", "&lt;\\1", value))
            ))
        except XMLSyntaxError:
            # if something went horribly wrong just don't bother with escaping
            element = Element('value')
            element.text = value
            return element

    def _get_col_key(self, translation_type, lang):
        """
        Returns the name of the column in the bulk app translation spreadsheet
        given the translation type and language
        :param translation_type: What is being translated, i.e. 'default' or 'image'
        :param lang:
        """
        return "%s_%s" % (translation_type, lang)
