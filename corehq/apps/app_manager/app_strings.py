import functools
from corehq.apps.app_manager import id_strings
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.app_manager.util import is_sort_only_column
import langcodes
import commcare_translations
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans


def non_empty_only(dct):
    return dict([(key, value) for key, value in dct.items() if value])


def _create_custom_app_strings(app, lang):

    def trans(d):
        return clean_trans(d, langs)

    def maybe_add_index(text):
        if app.build_version >= '2.8':
            numeric_nav_on = app.profile.get('properties', {}).get('cc-entry-mode') == 'cc-entry-review'
            if app.profile.get('features', {}).get('sense') == 'true' or numeric_nav_on:
                text = "${0} %s" % (text,) if not (text and text[0].isdigit()) else text
        return text

    langs = [lang] + app.langs
    yield id_strings.homescreen_title(), app.name
    yield id_strings.app_display_name(), app.name

    yield 'cchq.case', "Case"
    yield 'cchq.referral', "Referral"

    # include language code names
    for lc in app.langs:
        name = langcodes.get_name(lc) or lc
        if name:
            yield lc, name

    for module in app.get_modules():
        for detail_type, detail, _ in module.get_details():
            if detail_type.startswith('case'):
                label = trans(module.case_label)
            elif detail_type.startswith('referral'):
                label = trans(module.referral_label)
            else:
                label = None
            if label:
                yield id_strings.detail_title_locale(module, detail_type), label

            for column in detail.get_columns():
                if not is_sort_only_column(column):
                    yield id_strings.detail_column_header_locale(module, detail_type, column), trans(column.header)

                if column.format in ('enum', 'enum-image'):
                    for item in column.enum:
                        yield id_strings.detail_column_enum_variable(module, detail_type, column, item.key_as_variable), trans(item.value)
                elif column.format == "graph":
                    for index, item in enumerate(column.graph_configuration.annotations):
                        yield id_strings.graph_annotation(module, detail_type, column, index), trans(item.values)
                    for property, values in column.graph_configuration.locale_specific_config.iteritems():
                        yield id_strings.graph_configuration(module, detail_type, column, property), trans(values)

            for tab in detail.get_tabs():
                yield id_strings.detail_tab_title_locale(module, detail_type, tab), trans(tab.header)

        yield id_strings.module_locale(module), maybe_add_index(trans(module.name))
        if hasattr(module, 'report_configs'):
            for config in module.report_configs:
                yield id_strings.report_command(config.report_id), trans(config.header)
                yield id_strings.report_name(config.report_id), config.report.title
                yield id_strings.report_menu(), 'Reports'
                yield id_strings.report_name_header(), 'Report Name'
                yield id_strings.report_description_header(), 'Report Description'
                for column in config.report.report_columns:
                    yield (
                        id_strings.report_column_header(config.report_id, column.column_id),
                        column.get_header(lang)
                    )

        if hasattr(module, 'case_list'):
            if module.case_list.show:
                yield id_strings.case_list_locale(module), trans(module.case_list.label) or "Case List"
        if hasattr(module, 'referral_list'):
            if module.referral_list.show:
                yield id_strings.referral_list_locale(module), trans(module.referral_list.label)
        for form in module.get_forms():
            form_name = trans(form.name) + ('${0}' if form.show_count else '')
            yield id_strings.form_locale(form), maybe_add_index(form_name)

        if hasattr(module, 'case_list_form') and module.case_list_form.form_id:
            yield (
                id_strings.case_list_form_locale(module),
                trans(module.case_list_form.label) or "Create a new Case"
            )


class AppStringsBase(object):

    def __init__(self, load_translations):
        self._load_translations = load_translations

    @memoized
    def get_default_translations(self, lang):
        return self._load_translations(lang)

    def create_custom_app_strings(self, app, lang, for_default=False):
        custom = dict(_create_custom_app_strings(app, lang))
        if not for_default:
            custom = non_empty_only(custom)
        return custom

    def create_app_strings(self, app, lang, for_default=False):
        messages = {}
        for part in self.app_strings_parts(app, lang, for_default=for_default):
            messages.update(part)
        return commcare_translations.dumps(messages).encode('utf-8')

    def app_strings_parts(self, app, lang, for_default=False):
        raise NotImplementedError()

    def create_default_app_strings(self, app):
        messages = {}

        for lc in reversed(app.langs):
            if lc == "default":
                continue
            new_messages = commcare_translations.loads(
                self.create_app_strings(app, lc, for_default=True)
            )

            for key, val in new_messages.items():
                # do not overwrite a real trans with a blank trans
                if not (val == '' and key in messages):
                    messages[key] = val

        if 'case_sharing.exactly_one_group' not in messages:
            messages['case_sharing.exactly_one_group'] = \
                (u'The case sharing settings for your user are incorrect. '
                 u'This user must be in exactly one case sharing group. Please contact your supervisor.')

        if 'case_autoload.fixture.exactly_one_fixture' not in messages:
            messages['case_autoload.fixture.exactly_one_fixture'] = \
                (u'The lookup table settings for your user are incorrect. '
                    u'This user must have access to exactly one lookup table row for the table: ${0}')

        from corehq.apps.app_manager.models import (
            AUTO_SELECT_CASE, AUTO_SELECT_FIXTURE, AUTO_SELECT_USER,
            AUTO_SELECT_LOCATION, AUTO_SELECT_USERCASE, AUTO_SELECT_RAW
        )

        mode_text = {
            AUTO_SELECT_FIXTURE: u'lookup table field',
            AUTO_SELECT_USER: u'user data key',
            AUTO_SELECT_CASE: u'case index',
            AUTO_SELECT_USERCASE: u'user case',
            AUTO_SELECT_RAW: u'custom xpath expression',
        }

        for mode, text in mode_text.items():
            key = 'case_autoload.{0}.property_missing'.format(mode)
            if key not in messages:
                messages[key] = (u'The {} specified for case auto-selecting '
                                 u'could not be found: ${{0}}').format(text)
            key = 'case_autoload.{0}.case_missing'.format(mode)
            if key not in messages:
                messages[key] = u'Unable to find case referenced by auto-select case ID.'

        key = 'case_autoload.{0}.property_missing'.format(AUTO_SELECT_LOCATION)
        messages[key] = (u"This form requires access to the user's location, "
                         "but none was found.")
        key = 'case_autoload.{0}.case_missing'.format(AUTO_SELECT_LOCATION)
        messages[key] = (u"This form requires the user's location to be "
                         "marked as 'Tracks Stock'.")

        return commcare_translations.dumps(messages).encode('utf-8')


class DumpKnownAppStrings(AppStringsBase):

    def app_strings_parts(self, app, lang, for_default=False):
        yield self.create_custom_app_strings(app, lang, for_default=for_default)
        yield self.get_default_translations(lang)
        yield non_empty_only(app.translations.get(lang, {}))


class SimpleAppStrings(AppStringsBase):

    def app_strings_parts(self, app, lang, for_default=False):
        yield self.create_custom_app_strings(app, lang, for_default=for_default)
        if not for_default:
            yield non_empty_only(app.translations.get(lang, {}))


class SelectKnownAppStrings(AppStringsBase):

    def get_app_translation_keys(self, app):
        return set.union(set(), *(
            set(t.keys()) for t in app.translations.values()
        ))

    def app_strings_parts(self, app, lang, for_default=False):
        yield self.create_custom_app_strings(app, lang,
                                             for_default=for_default)
        cc_trans = self.get_default_translations(lang)
        yield dict((key, cc_trans[key])
                   for key in self.get_app_translation_keys(app)
                   if key in cc_trans)
        yield non_empty_only(app.translations.get(lang, {}))


CHOICES = {
    'dump-known': DumpKnownAppStrings(commcare_translations.load_translations),
    'simple': SimpleAppStrings(None),
    'select-known': SelectKnownAppStrings(
        functools.partial(commcare_translations.load_translations, version=2)
    ),
}
