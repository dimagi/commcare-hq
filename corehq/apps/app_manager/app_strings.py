from __future__ import absolute_import
from __future__ import unicode_literals
import functools
from distutils.version import LooseVersion

from django.utils.translation import ugettext

from corehq.apps.app_manager import id_strings
from memoized import memoized
from corehq.apps.app_manager.util import module_offers_search,\
    create_temp_sort_column, get_sort_and_sort_only_columns
import langcodes
import commcare_translations
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.util.translation import localize
from langcodes import langs_by_code
import six
from corehq import toggles


def non_empty_only(dct):
    return {key: value for key, value in dct.items() if value}


def convert_to_two_letter_code(lc):
    if len(lc) == 2:
        return lc

    lang = langs_by_code.get(lc)
    if lang:
        return lang['two']
    return lc


def _get_custom_icon_app_locale_and_value(custom_icon_form, custom_icon_text, form=None, module=None):
    if form:
        return id_strings.form_custom_icon_locale(form, custom_icon_form), custom_icon_text
    elif module:
        return id_strings.module_custom_icon_locale(module, custom_icon_form), custom_icon_text


def _create_custom_app_strings(app, lang, for_default=False, build_profile_id=None):
    # build_profile_id is relevant only if for_default is true

    def trans(d):
        return clean_trans(d, langs)

    def maybe_add_index(text):
        if app.build_version and app.build_version >= LooseVersion('2.8'):
            numeric_nav_on = app.profile.get('properties', {}).get('cc-entry-mode') == 'cc-entry-review'
            if app.profile.get('features', {}).get('sense') == 'true' or numeric_nav_on:
                text = "${0} %s" % (text,) if not (text and text[0].isdigit()) else text
        return text

    yield id_strings.homescreen_title(), app.name
    yield id_strings.app_display_name(), app.name

    for id, value in id_strings.REGEX_DEFAULT_VALUES.items():
        yield id, value

    ccz_langs = app.build_profiles[build_profile_id].langs if build_profile_id else app.langs
    langs = [lang] + ccz_langs
    if for_default:
        # include language code names and current language
        for lc in ccz_langs:
            name = langcodes.get_name(lc) or lc
            if not name:
                continue
            with localize(convert_to_two_letter_code(lc)):
                name = ugettext(name)
            yield lc, name

    yield id_strings.current_language(), lang

    for module in app.get_modules():
        for detail_type, detail, _ in module.get_details():
            for column in detail.get_columns():
                yield id_strings.detail_column_header_locale(module, detail_type, column), trans(column.header)

                if column.format in ('enum', 'enum-image', 'conditional-enum'):
                    for item in column.enum:
                        yield id_strings.detail_column_enum_variable(
                            module, detail_type, column, item.key_as_variable
                        ), trans(item.value)
                elif column.format == "graph":
                    for index, item in enumerate(column.graph_configuration.annotations):
                        yield id_strings.graph_annotation(module, detail_type, column, index), trans(item.values)
                    for property, values in six.iteritems(column.graph_configuration.locale_specific_config):
                        yield id_strings.graph_configuration(module, detail_type, column, property), trans(values)
                    for index, item in enumerate(column.graph_configuration.series):
                        for property, values in six.iteritems(item.locale_specific_config):
                            yield id_strings.graph_series_configuration(
                                module, detail_type, column, index, property
                            ), trans(values)

            # To list app strings for properties used as sorting properties only
            if detail.sort_elements:
                sort_only, sort_columns = get_sort_and_sort_only_columns(detail, detail.sort_elements)
                for field, sort_element, order in sort_only:
                    if sort_element.has_display_values():
                        column = create_temp_sort_column(sort_element, order)
                        yield id_strings.detail_column_header_locale(module, detail_type, column), \
                            trans(column.header)

            for tab in detail.get_tabs():
                yield id_strings.detail_tab_title_locale(module, detail_type, tab), trans(tab.header)

            if getattr(detail, 'lookup_display_results'):
                yield id_strings.callout_header_locale(module), trans(detail.lookup_field_header)

        yield id_strings.module_locale(module), maybe_add_index(trans(module.name))

        if toggles.APP_BUILDER_CONDITIONAL_NAMES.enabled(app.domain) and getattr(module, 'name_enum', None):
            for item in module.name_enum:
                yield id_strings.module_name_enum_variable(module, item.key_as_variable), trans(item.value)

        icon = module.icon_app_string(lang, for_default=for_default, build_profile_id=build_profile_id)
        audio = module.audio_app_string(lang, for_default=for_default, build_profile_id=build_profile_id)
        custom_icon_form, custom_icon_text = module.custom_icon_form_and_text_by_language(lang)
        if icon:
            yield id_strings.module_icon_locale(module), icon
        if audio:
            yield id_strings.module_audio_locale(module), audio
        if custom_icon_form and custom_icon_text:
            yield _get_custom_icon_app_locale_and_value(custom_icon_form, custom_icon_text, module=module)

        if hasattr(module, 'report_configs'):
            for config in module.report_configs:
                yield id_strings.report_command(config.uuid), trans(config.header)
                yield id_strings.report_name(config.uuid), trans(config.header)
                yield id_strings.report_description(config.uuid), trans(config.localized_description)
                for column in config.report(app.domain).report_columns:
                    yield (
                        id_strings.report_column_header(config.uuid, column.column_id),
                        column.get_header(lang)
                    )
                for chart_id, graph_config in six.iteritems(config.complete_graph_configs):
                    for index, item in enumerate(graph_config.annotations):
                        yield id_strings.mobile_ucr_annotation(module, config.uuid, index), trans(item.values)
                    for property, values in six.iteritems(graph_config.locale_specific_config):
                        yield id_strings.mobile_ucr_configuration(module, config.uuid, property), trans(values)
                    for index, item in enumerate(graph_config.series):
                        for property, values in six.iteritems(item.locale_specific_config):
                            yield id_strings.mobile_ucr_series_configuration(
                                module, config.uuid, index, property
                            ), trans(values)

        if hasattr(module, 'case_list'):
            if module.case_list.show:
                yield id_strings.case_list_locale(module), trans(module.case_list.label) or "Case List"
                icon = module.case_list.icon_app_string(lang, for_default=for_default,
                                                        build_profile_id=build_profile_id)
                audio = module.case_list.audio_app_string(lang, for_default=for_default,
                                                          build_profile_id=build_profile_id)
                if icon:
                    yield id_strings.case_list_icon_locale(module), icon
                if audio:
                    yield id_strings.case_list_audio_locale(module), audio

        if module_offers_search(module):
            yield id_strings.case_search_locale(module), trans(module.search_config.command_label)
            # icon and audio not yet available
            for prop in module.search_config.properties:
                yield id_strings.search_property_locale(module, prop.name), trans(prop.label)

        if hasattr(module, 'referral_list'):
            if module.referral_list.show:
                yield id_strings.referral_list_locale(module), trans(module.referral_list.label)
        for form in module.get_forms():
            form_name = trans(form.name) + ('${0}' if form.show_count else '')
            yield id_strings.form_locale(form), maybe_add_index(form_name)

            if toggles.APP_BUILDER_CONDITIONAL_NAMES.enabled(app.domain) and getattr(module, 'name_enum', None):
                for item in form.name_enum:
                    yield id_strings.form_name_enum_variable(form, item.key_as_variable), trans(item.value)

            icon = form.icon_app_string(lang, for_default=for_default, build_profile_id=build_profile_id)
            audio = form.audio_app_string(lang, for_default=for_default, build_profile_id=build_profile_id)
            custom_icon_form, custom_icon_text = form.custom_icon_form_and_text_by_language(lang)
            if icon:
                yield id_strings.form_icon_locale(form), icon
            if audio:
                yield id_strings.form_audio_locale(form), audio
            if custom_icon_form and custom_icon_text:
                yield _get_custom_icon_app_locale_and_value(custom_icon_form, custom_icon_text, form=form)

            for id, custom_assertion in enumerate(form.custom_assertions):
                yield id_strings.custom_assertion_locale(module, form, id), trans(custom_assertion.text)

        if hasattr(module, 'case_list_form') and module.case_list_form.form_id:
            yield (
                id_strings.case_list_form_locale(module),
                trans(module.case_list_form.label) or "Create a new Case"
            )
            icon = module.case_list_form.icon_app_string(lang, for_default=for_default,
                                                         build_profile_id=build_profile_id)
            audio = module.case_list_form.audio_app_string(lang, for_default=for_default,
                                                           build_profile_id=build_profile_id)
            if icon:
                yield id_strings.case_list_form_icon_locale(module), icon
            if audio:
                yield id_strings.case_list_form_audio_locale(module), audio


class AppStringsBase(object):

    def __init__(self, load_translations):
        self._load_translations = load_translations

    @memoized
    def get_default_translations(self, lang, commcare_version):
        translations = self._load_translations(lang, commcare_version=commcare_version)
        for id, value in id_strings.REGEX_DEFAULT_VALUES.items():
            translations[id] = value
        return translations

    def create_custom_app_strings(self, app, lang, for_default=False, build_profile_id=None):
        custom = dict(_create_custom_app_strings(app, lang, for_default=for_default,
                                                 build_profile_id=build_profile_id))
        if not for_default:
            custom = non_empty_only(custom)
        return custom

    def create_app_strings(self, app, lang, for_default=False, build_profile_id=None):
        # build_profile_id is relevant only if for_default is true
        messages = {}
        for part in self.app_strings_parts(app, lang, for_default=for_default, build_profile_id=build_profile_id):
            messages.update(part)
        return commcare_translations.dumps(messages)

    def app_strings_parts(self, app, lang, for_default=False, build_profile_id=None):
        raise NotImplementedError()

    def create_default_app_strings(self, app, build_profile_id=None):
        messages = {}

        langs = app.get_build_langs(build_profile_id)
        for lc in reversed(langs):
            if lc == "default":
                continue
            new_messages = commcare_translations.loads(
                self.create_app_strings(app, lc, for_default=True, build_profile_id=build_profile_id)
            )

            for key, val in new_messages.items():
                # do not overwrite a real trans with a blank trans
                if not (val == '' and key in messages):
                    messages[key] = val

        if 'case_sharing.exactly_one_group' not in messages:
            messages['case_sharing.exactly_one_group'] = \
                ('The case sharing settings for your user are incorrect. '
                 'This user must be in exactly one case sharing group. Please contact your supervisor.')

        if 'case_autoload.fixture.exactly_one_fixture' not in messages:
            messages['case_autoload.fixture.exactly_one_fixture'] = \
                ('The lookup table settings for your user are incorrect. '
                    'This user must have access to exactly one lookup table row for the table: ${0}')

        if 'case_autoload.usercase.case_missing' not in messages:
            messages['usercase.missing_id'] = \
                ('This form affects the user case, but no user case id was found. '
                    'Please contact your supervisor.')

        from corehq.apps.app_manager.models import (
            AUTO_SELECT_CASE, AUTO_SELECT_FIXTURE, AUTO_SELECT_USER,
            AUTO_SELECT_LOCATION, AUTO_SELECT_USERCASE, AUTO_SELECT_RAW
        )

        mode_text = {
            AUTO_SELECT_FIXTURE: 'lookup table field',
            AUTO_SELECT_USER: 'user data key',
            AUTO_SELECT_CASE: 'case index',
            AUTO_SELECT_USERCASE: 'user case',
            AUTO_SELECT_RAW: 'custom xpath expression',
        }

        for mode, text in mode_text.items():
            key = 'case_autoload.{0}.property_missing'.format(mode)
            if key not in messages:
                messages[key] = ('The {} specified for case auto-selecting '
                                 'could not be found: ${{0}}').format(text)
            key = 'case_autoload.{0}.case_missing'.format(mode)
            if key not in messages:
                messages[key] = 'Unable to find case referenced by auto-select case ID.'

        key = 'case_autoload.{0}.property_missing'.format(AUTO_SELECT_LOCATION)
        messages[key] = ("This form requires access to the user's location, "
                         "but none was found.")
        key = 'case_autoload.{0}.case_missing'.format(AUTO_SELECT_LOCATION)
        messages[key] = ("This form requires the user's location to be "
                         "marked as 'Tracks Stock'.")

        return commcare_translations.dumps(messages)


class DumpKnownAppStrings(AppStringsBase):

    def app_strings_parts(self, app, lang, for_default=False, build_profile_id=None):
        commcare_version = app.build_version.vstring if app.build_version else None

        yield self.create_custom_app_strings(app, lang, for_default=for_default, build_profile_id=build_profile_id)
        yield self.get_default_translations(lang, commcare_version)
        yield non_empty_only(app.translations.get(lang, {}))


class SimpleAppStrings(AppStringsBase):

    def app_strings_parts(self, app, lang, for_default=False, build_profile_id=None):
        yield self.create_custom_app_strings(app, lang, for_default=for_default, build_profile_id=build_profile_id)
        if not for_default:
            yield non_empty_only(app.translations.get(lang, {}))


class SelectKnownAppStrings(AppStringsBase):
    """
    Like DumpKnownAppStrings, but instead of returning all default
    translations, only returns those used by the app.

    This is the default behaviour.
    """

    def get_app_translation_keys(self, app):
        return {k for t in app.translations.values() for k in t.keys()}

    def app_strings_parts(self, app, lang, for_default=False, build_profile_id=None):
        yield self.create_custom_app_strings(app, lang, for_default=for_default, build_profile_id=build_profile_id)
        commcare_version = app.build_version.vstring if app.build_version else None
        cc_trans = self.get_default_translations(lang, commcare_version)
        yield {key: cc_trans[key] for key in self.get_app_translation_keys(app) if key in cc_trans}
        yield non_empty_only(app.translations.get(lang, {}))


CHOICES = {
    'dump-known': DumpKnownAppStrings(commcare_translations.load_translations),
    'simple': SimpleAppStrings(None),
    'select-known': SelectKnownAppStrings(
        functools.partial(commcare_translations.load_translations, version=2)
    ),
}
