from __future__ import absolute_import
from django.utils.translation import ugettext as _
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.app_translations.app_translations import _update_translation_dict
from corehq.apps.app_manager.app_translations.structures import (
    LabelTranslation, ModuleTranslation, FormTranslation,
    ColumnTranslation, ValueContainer, AnnotationTranslation,
    SeriesTranslation
)


class BaseTranslationParser:
    def __init__(self, resource_translation):
        self.resource_translation = resource_translation
        if self.resource_translation.module_resource:
            self.translation = ModuleTranslation.wrap(self.resource_translation.translation)
        elif self.resource_translation.form_resource:
            self.translation = FormTranslation.wrap(self.resource_translation.translation)

    def update_id_string(self, id_string, translations, prefix, langs):
        if id_string not in self.translation.id_strings:
            self.translation.id_strings[id_string] = {}
        _update_translation_dict(
            prefix,
            self.translation.id_strings[id_string],
            translations, langs
        )

    def update_name(self, langs, translated_names, prefix="default_"):
        from corehq.apps.app_manager import id_strings
        _update_translation_dict(
            prefix,
            self.translation.name,
            translated_names, langs)
        id_string = None
        if self.resource_translation.module_resource:
            id_string = id_strings.module_locale(self.resource_translation.resource)
        elif self.resource_translation.form_resource:
            id_string = id_strings.form_locale(self.resource_translation.resource)
        if not id_string:
            raise Exception(_("Unable to generate id string"))
        self.update_id_string(id_string, translated_names, prefix, langs)

    def update(self, *args, **kwargs):
        raise NotImplementedError

    def save(self):
        self.resource_translation.translation = self.translation.to_json()
        self.resource_translation.save()


class ModuleTranslationParser(BaseTranslationParser):
    def columns(self, detail_type):
        return self.translation.case_details[detail_type].columns

    def column(self, detail_type, column_index):
        return self.columns(detail_type)[column_index]

    def ensure_base_dict(self, detail_type, column_index):
        """
        ensure that a barebone dict is present for a particular column and append if not present
        :param detail_type: short/long
        :param column_index: index of column
        """
        if len(self.columns(detail_type)) == column_index:
            self.columns(detail_type).append(ColumnTranslation())
        elif len(self.columns(detail_type)) < column_index:
            # trying to add a column out of order
            raise Exception("adding column out of order")

    def update(self, langs, translations, detail_type, column_index, column, column_attr,
               column_attr_index=None, column_attr_key=None, prefix='default_'):
        """
        update a column attr for a long/short column detail
        :param langs: langs supported by the app
        :param translations: translations dict
        :param detail_type: long/short
        :param column_index: index of column
        :param column_attr: the column attr to update like name, header, enum, graph_annotations etc
        :param column: the column/DetailColumn
        :param column_attr_index: index of column attr in the list if required
        :param column_attr_key: if translations need to be mapped to a key within column attr
        :param prefix: prefix required for mapping lang to translation in translations dict
        """
        getattr(self, "update_{}".format(column_attr))(
            prefix, langs, translations, detail_type, column_index,
            column=column,
            column_attr_index=column_attr_index,
            column_attr_key=column_attr_key,
        )

    def update_header(self, prefix, langs, translated_headers, detail_type, column_index, column, **kwargs):
        self.ensure_base_dict(detail_type, column_index)
        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).header,
            translated_headers, langs)
        id_string = id_strings.detail_column_header_locale(
            self.resource_translation.resource, '_'.join(['case', detail_type]), column)
        self.update_id_string(id_string, translated_headers, prefix, langs)

    def update_enum(self, prefix, langs, translated_enums, detail_type, column_index, column, column_attr_index,
                    column_attr_key):
        self.ensure_base_dict(detail_type, column_index)
        # if there is no entry for this enum index just add an empty placeholder for it
        if len(self.column(detail_type, column_index).enum) == column_attr_index:
            self.column(detail_type, column_index).enum.append(ValueContainer())
        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).enum[column_attr_index].value,
            translated_enums, langs
        )
        id_string = id_strings.detail_column_enum_variable(
            self.resource_translation.resource, '_'.join(['case', detail_type]), column, column_attr_key)
        self.update_id_string(id_string, translated_enums, prefix, langs)

    def update_graph_annotations(self, prefix, langs, translated_annotations, detail_type, column_index, column,
                                 column_attr_index, **kwargs):
        self.ensure_base_dict(detail_type, column_index)
        # if there is no entry for this annotation index just add an empty placeholder for it
        if len(self.column(detail_type, column_index).graph_configuration.annotations) == column_attr_index:
            self.column(detail_type, column_index).graph_configuration.annotations.append(AnnotationTranslation())
        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).graph_configuration.annotations[column_attr_index].display_text,
            translated_annotations, langs
        )

        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).graph_configuration.annotations[
                column_attr_index].values,
            translated_annotations, langs
        )

        id_string = id_strings.graph_annotation(
            self.resource_translation.resource, '_'.join(['case', detail_type]), column, column_attr_index)
        self.update_id_string(id_string, translated_annotations, prefix, langs)

    def update_graph_configuration_config(self, prefix, langs, translated_configs, detail_type, column_index, column,
                                          **kwargs):
        self.ensure_base_dict(detail_type, column_index)
        key = kwargs['column_attr_key']
        # if there is no entry for the key just add an empty placeholder for it
        if key not in self.column(detail_type, column_index).graph_configuration.locale_specific_config:
            self.column(detail_type, column_index).graph_configuration.locale_specific_config[key] = {}
        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).graph_configuration.locale_specific_config[
                key],
            translated_configs, langs
        )
        id_string = id_strings.graph_configuration(
            self.resource_translation.resource, '_'.join(['case', detail_type]), column, key)
        self.update_id_string(id_string, translated_configs, prefix, langs)

    def update_graph_configuration_series(self, prefix, langs, translated_series_configs, detail_type, column_index,
                                          column, column_attr_index, column_attr_key):
        # if there is no entry for this series index just add an empty placeholder for it
        if len(self.column(detail_type, column_index).graph_configuration.series) == column_attr_index:
            self.column(detail_type, column_index).graph_configuration.series.append(
                SeriesTranslation())

        # if there is no entry for the key in this series index just add an empty placeholder for it
        if (column_attr_key not in
                self.column(detail_type, column_index)
                    .graph_configuration.series[column_attr_index].locale_specific_config):
            self.column(detail_type, column_index).graph_configuration.series[column_attr_index]\
                .locale_specific_config[column_attr_key] = {}
        _update_translation_dict(
            prefix,
            self.column(detail_type, column_index).graph_configuration.series[column_attr_index]
                .locale_specific_config[column_attr_key],
            translated_series_configs, langs
        )
        id_string = id_strings.graph_series_configuration(
            self.resource_translation.resource, '_'.join(['case', detail_type]), column,
            column_attr_index, column_attr_key)
        self.update_id_string(id_string, translated_series_configs, prefix, langs)


class FormTranslationParser(BaseTranslationParser):
    def ensure_base_dict(self, label_id):
        if label_id not in self.translation.text:
            self.translation.text[label_id] = LabelTranslation()

    def update(self, label_id, trans_type, lang, translation, delete_value_node):
        if delete_value_node:
            self.translation.text[label_id][trans_type].value = {}
        else:
            self.ensure_base_dict(label_id)
            self.translation.text[label_id][trans_type].value[lang] = translation
