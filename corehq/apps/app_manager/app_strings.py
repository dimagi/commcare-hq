import functools
from looseversion import LooseVersion

from django.utils.translation import gettext

import commcare_translations
import langcodes
from langcodes import langs_by_code
from memoized import memoized

from corehq import toggles
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.commcare_settings import (
    get_commcare_settings_lookup,
)
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.app_manager.util import (
    create_temp_sort_column,
    get_sort_and_sort_only_columns,
    module_offers_search,
)
from corehq.util.translation import localize


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
                name = gettext(name)
            yield lc, name

    yield id_strings.current_language(), lang

    for id, custom_assertion in enumerate(app.custom_assertions):
        yield (
            id_strings.custom_assertion_locale(id),
            clean_trans(custom_assertion.text, langs)
        )

    for module in app.get_modules():
        yield from _create_module_details_app_strings(module, langs)

        yield (
            id_strings.module_locale(module),
            _maybe_add_index(clean_trans(module.name, langs), app)
        )

        for id, custom_assertion in enumerate(module.custom_assertions):
            yield (
                id_strings.custom_assertion_locale(id, module),
                clean_trans(custom_assertion.text, langs)
            )

        yield from _create_icon_audio_app_strings(
            module,
            lang,
            for_default,
            build_profile_id,
        )

        yield from _create_report_configs_app_strings(app, module, lang, langs)

        yield from _create_case_list_app_strings(
            module,
            lang,
            langs,
            for_default,
            build_profile_id,
        )

        yield from _create_case_search_app_strings(
            app,
            module,
            lang,
            langs,
            for_default,
            build_profile_id,
        )

        yield from _create_referral_list_app_strings(module, langs)

        yield from _create_forms_app_strings(
            app,
            module,
            lang,
            langs,
            for_default,
            build_profile_id,
        )

        yield from _create_case_list_form_app_strings(
            app,
            module,
            lang,
            langs,
            for_default,
            build_profile_id,
        )

    yield from _create_dependencies_app_strings(app)


def _create_module_details_app_strings(module, langs):
    if module.get_app().supports_empty_case_list_text and hasattr(module, 'case_details'):
        yield (
            id_strings.no_items_text_detail(module),
            clean_trans(module.case_details.short.no_items_text, langs)
        )

    if module.get_app().supports_select_text and hasattr(module, 'case_details'):
        yield (
            id_strings.select_text_detail(module),
            clean_trans(module.case_details.short.select_text, langs)
        )

    for detail_type, detail, _ in module.get_details():
        for column in detail.get_columns():
            yield (
                id_strings.detail_column_header_locale(module, detail_type, column),
                clean_trans(column.header, langs)
            )

            if column.format in ('enum', 'conditional-enum', 'enum-image', 'clickable-icon'):
                for item in column.enum:
                    yield (
                        id_strings.detail_column_enum_variable(
                            module,
                            detail_type,
                            column,
                            item.key_as_variable,
                        ),
                        clean_trans(item.value, langs)
                    )
                    if module.get_app().supports_alt_text and column.format in ('enum-image', 'clickable-icon'):
                        yield (
                            id_strings.detail_column_alt_text_variable(
                                module,
                                detail_type,
                                column,
                                item.key_as_variable,
                            ),
                            clean_trans(item.alt_text, langs)
                        )
            elif column.format == "graph":
                for index, item in enumerate(column.graph_configuration.annotations):
                    yield (
                        id_strings.graph_annotation(
                            module,
                            detail_type,
                            column,
                            index,
                        ),
                        clean_trans(item.values, langs)
                    )

                items = column.graph_configuration.locale_specific_config.items()
                for property, values in items:
                    yield (
                        id_strings.graph_configuration(
                            module,
                            detail_type,
                            column,
                            property,
                        ),
                        clean_trans(values, langs)
                    )
                for index, item in enumerate(column.graph_configuration.series):
                    for property, values in item.locale_specific_config.items():
                        yield (
                            id_strings.graph_series_configuration(
                                module,
                                detail_type,
                                column,
                                index,
                                property,
                            ),
                            clean_trans(values, langs)
                        )

        # To list app strings for properties used as sorting properties only
        if detail.sort_elements:
            sort_only, sort_columns = get_sort_and_sort_only_columns(
                list(detail.get_columns()),  # evaluate generator
                detail.sort_elements,
            )
            for field, sort_element, order in sort_only:
                if sort_element.has_display_values():
                    column = create_temp_sort_column(sort_element, order)
                    yield (
                        id_strings.detail_column_header_locale(
                            module,
                            detail_type,
                            column,
                        ),
                        clean_trans(column.header, langs)
                    )

        for tab in detail.get_tabs():
            yield (
                id_strings.detail_tab_title_locale(module, detail_type, tab),
                clean_trans(tab.header, langs)
            )

        if getattr(detail, 'lookup_display_results'):
            yield (
                id_strings.callout_header_locale(module),
                clean_trans(detail.lookup_field_header, langs)
            )


def _create_icon_audio_app_strings(
    module,
    lang,
    for_default,
    build_profile_id,
):
    icon = module.icon_app_string(lang, for_default, build_profile_id)
    if icon:
        yield id_strings.module_icon_locale(module), icon

    audio = module.audio_app_string(lang, for_default, build_profile_id)
    if audio:
        yield id_strings.module_audio_locale(module), audio

    icon_form, icon_text = module.custom_icon_form_and_text_by_language(lang)
    if icon_form and icon_text:
        yield _get_custom_icon_app_locale_and_value(
            icon_form,
            icon_text,
            module=module,
        )


def _create_report_configs_app_strings(app, module, lang, langs):
    if hasattr(module, 'report_configs'):
        for config in module.report_configs:
            yield (
                id_strings.report_command(config.uuid),
                clean_trans(config.header, langs)
            )
            yield (
                id_strings.report_name(config.uuid),
                clean_trans(config.header, langs)
            )
            yield (
                id_strings.report_description(config.uuid),
                clean_trans(config.localized_description, langs)
            )
            for column in config.report(app.domain).report_columns:
                yield (
                    id_strings.report_column_header(config.uuid, column.column_id),
                    column.get_header(lang)
                )
            for chart_id, graph_config in config.complete_graph_configs.items():
                for index, item in enumerate(graph_config.annotations):
                    yield (
                        id_strings.mobile_ucr_annotation(module, config.uuid, index),
                        clean_trans(item.values, langs)
                    )
                for property, values in graph_config.locale_specific_config.items():
                    yield (
                        id_strings.mobile_ucr_configuration(
                            module,
                            config.uuid,
                            property,
                        ),
                        clean_trans(values, langs)
                    )
                for index, item in enumerate(graph_config.series):
                    for property, values in item.locale_specific_config.items():
                        yield (
                            id_strings.mobile_ucr_series_configuration(
                                module,
                                config.uuid,
                                index,
                                property,
                            ),
                            clean_trans(values, langs)
                        )


def _create_case_list_app_strings(
    module,
    lang,
    langs,
    for_default,
    build_profile_id,
):
    if hasattr(module, 'case_list'):
        if module.case_list.show:
            yield (
                id_strings.case_list_locale(module),
                clean_trans(module.case_list.label, langs) or "Case List"
            )

            icon = module.case_list.icon_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if icon:
                yield id_strings.case_list_icon_locale(module), icon

            audio = module.case_list.audio_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if audio:
                yield id_strings.case_list_audio_locale(module), audio


def _create_case_search_app_strings(
    app,
    module,
    lang,
    langs,
    for_default,
    build_profile_id,
):
    if module_offers_search(module):
        from corehq.apps.app_manager.models import CaseSearch

        if toggles.USH_CASE_CLAIM_UPDATES.enabled(app.domain):
            # search label
            yield (
                id_strings.case_search_locale(module),
                clean_trans(module.search_config.search_label.label, langs)
            )
            icon = module.search_config.search_label.icon_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if icon:
                yield id_strings.case_search_icon_locale(module), icon
            audio = module.search_config.search_label.audio_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if audio:
                yield id_strings.case_search_audio_locale(module), audio

            title_label = module.search_config.get_search_title_label(app, lang, for_default=for_default)
            if app.enable_case_search_title_translation:
                yield id_strings.case_search_title_translation(module), title_label

            yield (
                id_strings.case_search_description_locale(module),
                clean_trans(module.search_config.description, langs)
            )

            # search again label
            yield (
                id_strings.case_search_again_locale(module),
                clean_trans(module.search_config.search_again_label.label, langs)
            )
            icon = module.search_config.search_again_label.icon_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if icon:
                yield id_strings.case_search_again_icon_locale(module), icon
            audio = module.search_config.search_again_label.audio_app_string(
                lang,
                for_default,
                build_profile_id,
            )
            if audio:
                yield id_strings.case_search_again_audio_locale(module), audio
        else:
            yield (
                id_strings.case_search_title_translation(module),
                clean_trans(CaseSearch.title_label.default(), langs)
            )
            yield (
                id_strings.case_search_description_locale(module),
                clean_trans(CaseSearch.description.default(), langs)
            )
            yield (
                id_strings.case_search_locale(module),
                clean_trans(CaseSearch.search_label.default().label, langs)
            )
            yield (
                id_strings.case_search_again_locale(module),
                clean_trans(CaseSearch.search_again_label.default().label, langs)
            )

        for prop in module.search_config.properties:
            yield (
                id_strings.search_property_locale(module, prop.name),
                clean_trans(prop.label, langs)
            )
            yield (
                id_strings.search_property_hint_locale(module, prop.name),
                clean_trans(prop.hint, langs)
            )
            if prop.required.test:
                yield (
                    id_strings.search_property_required_text(module, prop.name),
                    clean_trans(prop.required.text, langs)
                )
            for i, validation in enumerate(prop.validations):
                if validation.has_text:
                    yield (
                        id_strings.search_property_validation_text(
                            module,
                            prop.name,
                            i,
                        ),
                        clean_trans(validation.text, langs)
                    )


def _create_referral_list_app_strings(module, langs):
    if hasattr(module, 'referral_list'):
        if module.referral_list.show:
            yield (
                id_strings.referral_list_locale(module),
                clean_trans(module.referral_list.label, langs)
            )


def _create_forms_app_strings(
    app,
    module,
    lang,
    langs,
    for_default,
    build_profile_id,
):
    for form in module.get_forms():
        if form.show_count:
            form_name = clean_trans(form.name, langs) + '${0}'
        else:
            form_name = clean_trans(form.name, langs)
        yield id_strings.form_locale(form), _maybe_add_index(form_name, app)

        icon = form.icon_app_string(lang, for_default, build_profile_id)
        if icon:
            yield id_strings.form_icon_locale(form), icon

        audio = form.audio_app_string(lang, for_default, build_profile_id)
        if audio:
            yield id_strings.form_audio_locale(form), audio

        icon_form, icon_text = form.custom_icon_form_and_text_by_language(lang)
        if icon_form and icon_text:
            yield _get_custom_icon_app_locale_and_value(
                icon_form,
                icon_text,
                form=form,
            )

        for id, custom_assertion in enumerate(form.custom_assertions):
            yield (
                id_strings.custom_assertion_locale(id, module, form),
                clean_trans(custom_assertion.text, langs)
            )

        yield id_strings.form_submit_label_locale(form), form.get_submit_label(lang)
        if form.get_submit_notification_label(lang):
            yield id_strings.form_submit_notification_label_locale(form), form.get_submit_notification_label(lang)


def _create_case_list_form_app_strings(
    app,
    module,
    lang,
    langs,
    for_default,
    build_profile_id,
):
    if hasattr(module, 'case_list_form') and module.case_list_form.form_id:
        if toggles.FOLLOWUP_FORMS_AS_CASE_LIST_FORM.enabled(app.domain):
            form_name = app.get_form(module.case_list_form.form_id).name
            fallback_name = gettext("Continue To {form_name}").format(
                form_name=clean_trans(form_name, langs))
        else:
            fallback_name = gettext("Create a new Case")
        yield (
            id_strings.case_list_form_locale(module),
            clean_trans(module.case_list_form.label, langs) or fallback_name
        )

        icon = module.case_list_form.icon_app_string(
            lang,
            for_default,
            build_profile_id,
        )
        if icon:
            yield id_strings.case_list_form_icon_locale(module), icon

        audio = module.case_list_form.audio_app_string(
            lang,
            for_default,
            build_profile_id,
        )
        if audio:
            yield id_strings.case_list_form_audio_locale(module), audio


def _create_dependencies_app_strings(app):
    dependencies = app.profile.get('features', {}).get('dependencies')
    if toggles.APP_DEPENDENCIES.enabled(app.domain) and dependencies:
        settings = get_commcare_settings_lookup()['features']['dependencies']
        app_id_to_name = {k: v for k, v in zip(
            settings["values"],
            settings["value_names"]
        )}
        for app_id in dependencies:
            app_name = app_id_to_name[app_id]
            yield id_strings.android_package_name(app_id), app_name


def _maybe_add_index(text, app):
    if app.build_version and app.build_version >= LooseVersion('2.8'):
        sense_on = app.profile.get('features', {}).get('sense') == 'true'
        entry_mode = app.profile.get('properties', {}).get('cc-entry-mode')
        numeric_nav_on = entry_mode == 'cc-entry-review'
        starts_with_digit = text and text[0].isdigit()
        if (sense_on or numeric_nav_on) and not starts_with_digit:
            text = f"${{0}} {text}"
    return text


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
            messages['case_autoload.usercase.case_missing'] = \
                ('This form affects the user case, but no user case id was found. '
                    'Please contact your supervisor.')

        if 'case_search.claimed_case.case_missing' not in messages:
            messages['case_search.claimed_case.case_missing'] = \
                'Unable to find the selected case after performing a sync. Please try again.'

        from corehq.apps.app_manager.const import (
            AUTO_SELECT_CASE,
            AUTO_SELECT_FIXTURE,
            AUTO_SELECT_LOCATION,
            AUTO_SELECT_RAW,
            AUTO_SELECT_USER,
            AUTO_SELECT_USERCASE,
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
