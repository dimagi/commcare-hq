from collections import namedtuple, defaultdict
from itertools import izip_longest, chain
import os
import re
import urllib

from xml.sax.saxutils import escape

from django.utils.translation import ugettext_noop as _
from django.core.urlresolvers import reverse
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_SCHEDULE
from corehq.apps.app_manager.suite_xml.details import get_detail_column_infos, DetailContributor
from corehq.apps.app_manager.suite_xml.workflow import WorkflowHelper

from .exceptions import (
    MediaResourceError,
    ParentModuleReferenceError,
    SuiteError,
    SuiteValidationError,
)
from corehq.feature_previews import MODULE_FILTER
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    CAREPLAN_GOAL, CAREPLAN_TASK, SCHEDULE_LAST_VISIT,
    RETURN_TO, USERCASE_ID, USERCASE_TYPE, SCHEDULE_LAST_VISIT_DATE, SCHEDULE_DATE_CASE_OPENED,
    SCHEDULE_NEXT_DUE, SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
)
from corehq.apps.app_manager.exceptions import UnknownInstanceError, ScheduleError, FormNotFoundException
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import split_path, create_temp_sort_column, languages_mapping, \
    actions_use_usercase, is_usercase_in_use
from corehq.apps.app_manager.xform import autoset_owner_id_for_open_case, \
    autoset_owner_id_for_subcase
from corehq.apps.app_manager.xpath import interpolate_xpath, CaseIDXPath, session_var, \
    CaseTypeXpath, ItemListFixtureXpath, XPath, ProductInstanceXpath, UserCaseXPath, \
    ScheduleFormXPath, QualifiedScheduleFormXPath
from corehq.apps.hqmedia.models import HQMediaMapItem
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import get_url_base
from corehq.apps.app_manager.suite_xml.xml_models import *


class SuiteGeneratorBase(object):
    descriptor = None
    sections = ()

    def __init__(self, app):
        self.app = app
        # this is actually so slow it's worth caching
        self.modules = list(self.app.get_modules())

    def generate_suite(self):
        suite = Suite(
            version=self.app.version,
            descriptor=self.descriptor,
        )

        def add_to_suite(attr):
            getattr(suite, attr).extend(getattr(self, attr))

        map(add_to_suite, self.sections)
        self.post_process(suite)
        return suite.serializeDocument(pretty=True)

    def post_process(self, suite):
        pass


def get_instance_factory(scheme):
    return get_instance_factory._factory_map.get(scheme, preset_instances)
get_instance_factory._factory_map = {}


class register_factory(object):
    def __init__(self, *schemes):
        self.schemes = schemes

    def __call__(self, fn):
        for scheme in self.schemes:
            get_instance_factory._factory_map[scheme] = fn
        return fn


INSTANCE_BY_ID = {
    'groups': Instance(id='groups', src='jr://fixture/user-groups'),
    'reports': Instance(id='reports', src='jr://fixture/commcare:reports'),
    'ledgerdb': Instance(id='ledgerdb', src='jr://instance/ledgerdb'),
    'casedb': Instance(id='casedb', src='jr://instance/casedb'),
    'commcaresession': Instance(id='commcaresession', src='jr://instance/session'),
}

@register_factory(*INSTANCE_BY_ID.keys())
def preset_instances(instance_name):
    return INSTANCE_BY_ID.get(instance_name, None)


@register_factory('item-list', 'schedule', 'indicators', 'commtrack')
@memoized
def generic_fixture_instances(instance_name):
    return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


FormDatumMeta = namedtuple('FormDatumMeta', 'datum case_type requires_selection action')


class SuiteGenerator(SuiteGeneratorBase):
    descriptor = u"Suite File"
    sections = (
        'xform_resources',
        'locale_resources',
        'details',
        'entries',
        'menus',
        'fixtures',
    )

    def __init__(self, app):
        super(SuiteGenerator, self).__init__(app)
        self.detail_ids = {
            id_strings.detail(module, detail_type)
            for module in self.modules for detail_type, detail, enabled in module.get_details()
            if enabled and detail.columns
        }

    def post_process(self, suite):
        if self.app.enable_post_form_workflow:
            WorkflowHelper(suite, self.app, self.modules).add_form_workflow()

        details_by_id = self.get_detail_mapping()
        relevance_by_menu, menu_by_command = self.get_menu_relevance_mapping()
        for e in suite.entries:
            self.add_referenced_instances(e, details_by_id, relevance_by_menu, menu_by_command)

    @property
    def xform_resources(self):
        first = []
        last = []
        for form_stuff in self.app.get_forms(bare=False):
            form = form_stuff["form"]
            if form_stuff['type'] == 'module_form':
                path = './modules-{module.id}/forms-{form.id}.xml'.format(**form_stuff)
                this_list = first
            else:
                path = './user_registration.xml'
                this_list = last
            resource = XFormResource(
                id=id_strings.xform_resource(form),
                version=form.get_version(),
                local=path,
                remote=path,
            )
            if form_stuff['type'] == 'module_form' and self.app.build_version >= '2.9':
                resource.descriptor = u"Form: (Module {module_name}) - {form_name}".format(
                    module_name=trans(form_stuff["module"]["name"], langs=[self.app.default_language]),
                    form_name=trans(form["name"], langs=[self.app.default_language])
                )
            elif path == './user_registration.xml':
                resource.descriptor=u"User Registration Form"
            this_list.append(resource)
        for x in first:
            yield x
        for x in last:
            yield x

    @property
    def locale_resources(self):
        for lang in ["default"] + self.app.build_langs:
            path = './{lang}/app_strings.txt'.format(lang=lang)
            resource = LocaleResource(
                language=lang,
                id=id_strings.locale_resource(lang),
                version=self.app.version,
                local=path,
                remote=path,
            )
            if self.app.build_version >= '2.9':
                unknown_lang_txt = u"Unknown Language (%s)" % lang
                resource.descriptor = u"Translations: %s" % languages_mapping().get(lang, [unknown_lang_txt])[0]
            yield resource

    def get_datums_meta_for_form_generic(self, form):
        if form.form_type == 'module_form':
            datums_meta = self.get_case_datums_basic_module(form.get_module(), form)
        elif form.form_type == 'advanced_form':
            datums_meta, _ = self.get_datum_meta_assertions_advanced(form.get_module(), form)
            datums_meta.extend(SuiteGenerator.get_new_case_id_datums_meta(form))
        else:
            raise SuiteError("Unexpected form type '{}' with a case list form: {}".format(
                form.form_type, form.unique_id
            ))
        return datums_meta

    def _add_action_to_detail(self, detail, module):
        # add form action to detail
        form = self.app.get_form(module.case_list_form.form_id)

        if self.app.enable_localized_menu_media:
            case_list_form = module.case_list_form
            detail.action = LocalizedAction(
                menu_locale_id=id_strings.case_list_form_locale(module),
                media_image=bool(len(case_list_form.all_image_paths())),
                media_audio=bool(len(case_list_form.all_audio_paths())),
                image_locale_id=id_strings.case_list_form_icon_locale(module),
                audio_locale_id=id_strings.case_list_form_audio_locale(module),
                stack=Stack(),
                for_action_menu=True,
            )
        else:
            detail.action = Action(
                display=Display(
                    text=Text(locale_id=id_strings.case_list_form_locale(module)),
                    media_image=module.case_list_form.default_media_image,
                    media_audio=module.case_list_form.default_media_audio,
                ),
                stack=Stack()
            )

        frame = PushFrame()
        frame.add_command(XPath.string(id_strings.form_command(form)))

        target_form_dm = self.get_datums_meta_for_form_generic(form)
        source_form_dm = self.get_datums_meta_for_form_generic(module.get_form(0))
        for target_meta in target_form_dm:
            if target_meta.requires_selection:
                # This is true for registration forms where the case being created is a subcase
                try:
                    [source_dm] = [
                        source_meta for source_meta in source_form_dm
                        if source_meta.case_type == target_meta.case_type
                    ]
                except ValueError:
                    raise SuiteError("Form selected as case list form requires a case "
                                     "but no matching case could be found: {}".format(form.unique_id))
                else:
                    frame.add_datum(StackDatum(
                        id=target_meta.datum.id,
                        value=session_var(source_dm.datum.id))
                    )
            else:
                s_datum = target_meta.datum
                frame.add_datum(StackDatum(id=s_datum.id, value=s_datum.function))

        frame.add_datum(StackDatum(id=RETURN_TO, value=XPath.string(id_strings.menu_id(module))))
        detail.action.stack.add_frame(frame)

    @property
    @memoized
    def details(self):
        return DetailContributor(self, self.app, self.modules).get_section_contributions()

    @staticmethod
    def get_filter_xpath(module, delegation=False):
        filter = module.case_details.short.filter
        if filter:
            xpath = '[%s]' % filter
        else:
            xpath = ''
        if delegation:
            xpath += "[index/parent/@case_type = '%s']" % module.case_type
            xpath += "[start_date = '' or double(date(start_date)) <= double(now())]"
        return xpath

    @staticmethod
    def get_nodeset_xpath(case_type, module, use_filter):
        return "instance('casedb')/casedb/case[@case_type='{case_type}'][@status='open']{filter_xpath}".format(
            case_type=case_type,
            filter_xpath=SuiteGenerator.get_filter_xpath(module) if use_filter else '',
        )

    @staticmethod
    def get_parent_filter(relationship, parent_id):
        return "[index/{relationship}=instance('commcaresession')/session/data/{parent_id}]".format(
            relationship=relationship,
            parent_id=parent_id,
        )

    @staticmethod
    def get_select_chain(app, module, include_self=True):
        select_chain = [module] if include_self else []
        current_module = module
        while hasattr(current_module, 'parent_select') and current_module.parent_select.active:
            current_module = app.get_module_by_unique_id(
                current_module.parent_select.module_id
            )
            select_chain.append(current_module)
        return select_chain

    @memoized
    def get_detail_mapping(self):
        return {detail.id: detail for detail in self.details}

    @memoized
    def get_menu_relevance_mapping(self):
        relevance_by_menu = defaultdict(list)
        menu_by_command = {}
        for menu in self.menus:
            for command in menu.commands:
                menu_by_command[command.id] = menu.id
                if command.relevant:
                    relevance_by_menu[menu.id].append(command.relevant)
            if menu.relevant:
                relevance_by_menu[menu.id].append(menu.relevant)

        return relevance_by_menu, menu_by_command

    def get_detail_id_safe(self, module, detail_type):
        detail_id = id_strings.detail(
            module=module,
            detail_type=detail_type,
        )
        return detail_id if detail_id in self.detail_ids else None

    def get_instances_for_module(self, module, additional_xpaths=None):
        """
        This method is used by CloudCare when filtering cases.
        """
        details_by_id = self.get_detail_mapping()
        detail_ids = [self.get_detail_id_safe(module, detail_type)
                      for detail_type, detail, enabled in module.get_details()
                      if enabled]
        detail_ids = filter(None, detail_ids)
        xpaths = set()

        if additional_xpaths:
            xpaths.update(additional_xpaths)

        for detail_id in detail_ids:
            xpaths.update(details_by_id[detail_id].get_all_xpaths())

        return SuiteGenerator.get_required_instances(xpaths)

    @staticmethod
    def get_required_instances(xpaths):
        instance_re = r"""instance\(['"]([\w\-:]+)['"]\)"""
        instances = set()
        for xpath in xpaths:
            instance_names = re.findall(instance_re, xpath)
            for instance_name in instance_names:
                try:
                    scheme, _ = instance_name.split(':', 1)
                except ValueError:
                    scheme = None

                factory = get_instance_factory(scheme)
                instance = factory(instance_name)
                if instance:
                    instances.add(instance)
                else:
                    raise UnknownInstanceError("Instance reference not recognized: {}".format(instance_name))
        return instances

    @staticmethod
    def add_referenced_instances(entry, details_by_id, relevance_by_menu, menu_by_command):
        detail_ids = set()
        xpaths = set()

        for datum in entry.datums:
            detail_ids.add(datum.detail_confirm)
            detail_ids.add(datum.detail_select)
            xpaths.add(datum.nodeset)
            xpaths.add(datum.function)
        details = [details_by_id[detail_id] for detail_id in detail_ids
                   if detail_id]

        entry_id = entry.command.id
        menu_id = menu_by_command[entry_id]
        relevances = relevance_by_menu[menu_id]
        xpaths.update(relevances)

        for detail in details:
            xpaths.update(detail.get_all_xpaths())
        for assertion in entry.assertions:
            xpaths.add(assertion.test)
        if entry.stack:
            for frame in entry.stack.frames:
                xpaths.add(frame.if_clause)
                if hasattr(frame, 'datums'):
                    for datum in frame.datums:
                        xpaths.add(datum.value)
        xpaths.discard(None)

        instances = SuiteGenerator.get_required_instances(xpaths)

        entry.require_instance(*instances)

    @staticmethod
    def get_userdata_autoselect(key, session_id, mode):
        base_xpath = session_var('data', path='user')
        xpath = session_var(key, path='user/data')
        protected_xpath = XPath.if_(
            XPath.and_(base_xpath.count().eq(1), xpath.count().eq(1)),
            xpath,
            XPath.empty_string(),
        )
        datum = SessionDatum(id=session_id, function=protected_xpath)
        assertions = [
            SuiteGenerator.get_assertion(
                XPath.and_(base_xpath.count().eq(1),
                           xpath.count().eq(1)),
                'case_autoload.{0}.property_missing'.format(mode),
                [key],
            ),
            SuiteGenerator.get_assertion(
                CaseIDXPath(xpath).case().count().eq(1),
                'case_autoload.{0}.case_missing'.format(mode),
            )
        ]
        return datum, assertions

    @property
    def entries(self):
        # avoid circular dependency
        from corehq.apps.app_manager.models import Module, AdvancedModule
        results = []
        for module in self.modules:
            for form in module.get_forms():
                e = Entry()
                e.form = form.xmlns
                # Ideally all of this version check should happen in Command/Display class
                if self.app.enable_localized_menu_media:
                    e.command = LocalizedCommand(
                        id=id_strings.form_command(form),
                        menu_locale_id=id_strings.form_locale(form),
                        media_image=bool(len(form.all_image_paths())),
                        media_audio=bool(len(form.all_audio_paths())),
                        image_locale_id=id_strings.form_icon_locale(form),
                        audio_locale_id=id_strings.form_audio_locale(form),
                    )
                else:
                    e.command = Command(
                        id=id_strings.form_command(form),
                        locale_id=id_strings.form_locale(form),
                        media_image=form.default_media_image,
                        media_audio=form.default_media_audio,
                    )
                config_entry = {
                    'module_form': self.configure_entry_module_form,
                    'advanced_form': self.configure_entry_advanced_form,
                    'careplan_form': self.configure_entry_careplan_form,
                }[form.form_type]
                config_entry(module, e, form)

                if (
                    self.app.commtrack_enabled and
                    session_var('supply_point_id') in getattr(form, 'source', "")
                ):
                    from .models import AUTO_SELECT_LOCATION
                    datum, assertions = SuiteGenerator.get_userdata_autoselect(
                        'commtrack-supply-point',
                        'supply_point_id',
                        AUTO_SELECT_LOCATION,
                    )
                    e.datums.append(datum)
                    e.assertions.extend(assertions)

                results.append(e)

            if hasattr(module, 'case_list') and module.case_list.show:
                e = Entry()
                if self.app.enable_localized_menu_media:
                    e.command = LocalizedCommand(
                        id=id_strings.case_list_command(module),
                        menu_locale_id=id_strings.case_list_locale(module),
                        media_image=bool(len(module.case_list.all_image_paths())),
                        media_audio=bool(len(module.case_list.all_audio_paths())),
                        image_locale_id=id_strings.case_list_icon_locale(module),
                        audio_locale_id=id_strings.case_list_audio_locale(module),
                    )
                else:
                    e.command = Command(
                        id=id_strings.case_list_command(module),
                        locale_id=id_strings.case_list_locale(module),
                        media_image=module.case_list.default_media_image,
                        media_audio=module.case_list.default_media_audio,
                    )
                if isinstance(module, Module):
                    for datum_meta in self.get_datum_meta_module(module, use_filter=False):
                        e.datums.append(datum_meta.datum)
                elif isinstance(module, AdvancedModule):
                    e.datums.append(SessionDatum(
                        id='case_id_case_%s' % module.case_type,
                        nodeset=(SuiteGenerator.get_nodeset_xpath(module.case_type, module, False)),
                        value="./@case_id",
                        detail_select=self.get_detail_id_safe(module, 'case_short'),
                        detail_confirm=self.get_detail_id_safe(module, 'case_long')
                    ))
                    if self.app.commtrack_enabled:
                        e.datums.append(SessionDatum(
                            id='product_id',
                            nodeset=ProductInstanceXpath().instance(),
                            value="./@id",
                            detail_select=self.get_detail_id_safe(module, 'product_short')
                        ))
                results.append(e)

            for entry in module.get_custom_entries():
                results.append(entry)

        return results

    @staticmethod
    def get_assertion(test, locale_id, locale_arguments=None):
        assertion = Assertion(test=test)
        text = Text(locale_id=locale_id)
        if locale_arguments:
            locale = text.locale
            for arg in locale_arguments:
                locale.arguments.append(LocaleArgument(value=arg))
        assertion.text.append(text)
        return assertion

    @staticmethod
    def add_case_sharing_assertion(entry):
        assertion = SuiteGenerator.get_assertion("count(instance('groups')/groups/group) = 1",
                           'case_sharing.exactly_one_group')
        entry.assertions.append(assertion)

    @staticmethod
    def get_auto_select_assertions(case_id_xpath, mode, locale_arguments=None):
        case_count = CaseIDXPath(case_id_xpath).case().count()
        return [
            SuiteGenerator.get_assertion(
                "{0} = 1".format(case_id_xpath.count()),
                'case_autoload.{0}.property_missing'.format(mode),
                locale_arguments
            ),
            SuiteGenerator.get_assertion(
                "{0} = 1".format(case_count),
                'case_autoload.{0}.case_missing'.format(mode),
            )
        ]

    @staticmethod
    def get_extra_case_id_datums(form):
        datums = []
        actions = form.active_actions()
        if form.form_type == 'module_form' and actions_use_usercase(actions):
            case = UserCaseXPath().case()
            datums.append(FormDatumMeta(
                datum=SessionDatum(id=USERCASE_ID, function=('%s/@case_id' % case)),
                case_type=USERCASE_TYPE,
                requires_selection=False,
                action=None  # Unused (and could be actions['usercase_update'] or actions['usercase_preload'])
            ))
        return datums

    @staticmethod
    def any_usercase_datums(datums):
        return any(d.case_type == USERCASE_TYPE for d in datums)

    @staticmethod
    def get_new_case_id_datums_meta(form):
        if not form:
            return []

        datums = []
        if form.form_type == 'module_form':
            actions = form.active_actions()
            if 'open_case' in actions:
                datums.append(FormDatumMeta(
                    datum=SessionDatum(id=form.session_var_for_action('open_case'), function='uuid()'),
                    case_type=form.get_module().case_type,
                    requires_selection=False,
                    action=actions['open_case']
                ))

            if 'subcases' in actions:
                for subcase in actions['subcases']:
                    # don't put this in the loop to be consistent with the form's indexing
                    # see XForm.create_casexml_2
                    if not subcase.repeat_context:
                        datums.append(FormDatumMeta(
                            datum=SessionDatum(
                                id=form.session_var_for_action(subcase), function='uuid()'
                            ),
                            case_type=subcase.case_type,
                            requires_selection=False,
                            action=subcase
                        ))
        elif form.form_type == 'advanced_form':
            for action in form.actions.get_open_actions():
                if not action.repeat_context:
                    datums.append(FormDatumMeta(
                        datum=SessionDatum(id=action.case_session_var, function='uuid()'),
                        case_type=action.case_type,
                        requires_selection=False,
                        action=action
                    ))

        return datums

    def get_case_datums_basic_module(self, module, form):
        datums = []
        if not form or form.requires_case():
            datums.extend(self.get_datum_meta_module(module, use_filter=True))
        datums.extend(SuiteGenerator.get_new_case_id_datums_meta(form))
        datums.extend(SuiteGenerator.get_extra_case_id_datums(form))
        self.add_parent_datums(datums, module)
        return datums

    def configure_entry_module_form(self, module, e, form=None, use_filter=True, **kwargs):
        def case_sharing_requires_assertion(form):
            actions = form.active_actions()
            if 'open_case' in actions and autoset_owner_id_for_open_case(actions):
                return True
            if 'subcases' in actions:
                for subcase in actions['subcases']:
                    if autoset_owner_id_for_subcase(subcase):
                        return True
            return False

        datums = self.get_case_datums_basic_module(module, form)
        for datum in datums:
            e.datums.append(datum.datum)

        if form and self.app.case_sharing and case_sharing_requires_assertion(form):
            SuiteGenerator.add_case_sharing_assertion(e)

    def _get_datums_meta(self, module):
        """
            return list of dicts containing datum IDs and case types
            [
               {'session_var': 'parent_parent_id', ... },
               {'session_var': 'parent_id', ...}
               {'session_var': 'child_id', ...},
            ]
        """
        if not (module and module.module_type == 'basic'):
            return []

        select_chain = SuiteGenerator.get_select_chain(self.app, module)
        return [
            {
                'session_var': ('parent_' * i or 'case_') + 'id',
                'case_type': mod.case_type,
                'module': mod,
                'index': i
            }
            for i, mod in reversed(list(enumerate(select_chain)))
        ]

    def get_datum_meta_module(self, module, use_filter=False):
        datums = []
        datums_meta = self._get_datums_meta(module)
        for i, datum in enumerate(datums_meta):
            # get the session var for the previous datum if there is one
            parent_id = datums_meta[i - 1]['session_var'] if i >= 1 else ''
            if parent_id:
                parent_filter = SuiteGenerator.get_parent_filter(datum['module'].parent_select.relationship, parent_id)
            else:
                parent_filter = ''

            detail_persistent = None
            detail_inline = False
            for detail_type, detail, enabled in datum['module'].get_details():
                if (
                    detail.persist_tile_on_forms
                    and (detail.use_case_tiles or detail.custom_xml)
                    and enabled
                ):
                    detail_persistent = id_strings.detail(datum['module'], detail_type)
                    detail_inline = bool(detail.pull_down_tile)
                    break

            fixture_select_filter = ''
            if datum['module'].fixture_select.active:
                datums.append(FormDatumMeta(
                    datum=SessionDatum(
                        id=id_strings.fixture_session_var(datum['module']),
                        nodeset=ItemListFixtureXpath(datum['module'].fixture_select.fixture_type).instance(),
                        value=datum['module'].fixture_select.variable_column,
                        detail_select=id_strings.fixture_detail(datum['module'])
                    ),
                    case_type=None,
                    requires_selection=True,
                    action='fixture_select'
                ))
                filter_xpath_template = datum['module'].fixture_select.xpath
                fixture_value = session_var(id_strings.fixture_session_var(datum['module']))
                fixture_select_filter = "[{}]".format(
                    filter_xpath_template.replace('$fixture_value', fixture_value)
                )

            datums.append(FormDatumMeta(
                datum=SessionDatum(
                    id=datum['session_var'],
                    nodeset=(SuiteGenerator.get_nodeset_xpath(datum['case_type'], datum['module'], use_filter)
                             + parent_filter + fixture_select_filter),
                    value="./@case_id",
                    detail_select=self.get_detail_id_safe(datum['module'], 'case_short'),
                    detail_confirm=(
                        self.get_detail_id_safe(datum['module'], 'case_long')
                        if datum['index'] == 0 and not detail_inline else None
                    ),
                    detail_persistent=detail_persistent,
                    detail_inline=self.get_detail_id_safe(datum['module'], 'case_long') if detail_inline else None
                ),
                case_type=datum['case_type'],
                requires_selection=True,
                action='update_case'
            ))
        return datums

    @staticmethod
    def get_auto_select_datums_and_assertions(action, auto_select, form):
        from corehq.apps.app_manager.models import AUTO_SELECT_USER, AUTO_SELECT_CASE, \
            AUTO_SELECT_FIXTURE, AUTO_SELECT_RAW, AUTO_SELECT_USERCASE
        if auto_select.mode == AUTO_SELECT_USER:
            return SuiteGenerator.get_userdata_autoselect(
                auto_select.value_key,
                action.case_session_var,
                auto_select.mode,
            )
        elif auto_select.mode == AUTO_SELECT_CASE:
            try:
                ref = form.actions.actions_meta_by_tag[auto_select.value_source]['action']
                sess_var = ref.case_session_var
            except KeyError:
                raise ValueError("Case tag not found: %s" % auto_select.value_source)
            xpath = CaseIDXPath(session_var(sess_var)).case().index_id(auto_select.value_key)
            assertions = SuiteGenerator.get_auto_select_assertions(xpath, auto_select.mode, [auto_select.value_key])
            return SessionDatum(
                id=action.case_session_var,
                function=xpath
            ), assertions
        elif auto_select.mode == AUTO_SELECT_FIXTURE:
            xpath_base = ItemListFixtureXpath(auto_select.value_source).instance()
            xpath = xpath_base.slash(auto_select.value_key)
            fixture_assertion = SuiteGenerator.get_assertion(
                "{0} = 1".format(xpath_base.count()),
                'case_autoload.{0}.exactly_one_fixture'.format(auto_select.mode),
                [auto_select.value_source]
            )
            assertions = SuiteGenerator.get_auto_select_assertions(xpath, auto_select.mode, [auto_select.value_key])
            return SessionDatum(
                id=action.case_session_var,
                function=xpath
            ), [fixture_assertion] + assertions
        elif auto_select.mode == AUTO_SELECT_RAW:
            case_id_xpath = auto_select.value_key
            case_count = CaseIDXPath(case_id_xpath).case().count()
            return SessionDatum(
                id=action.case_session_var,
                function=case_id_xpath
            ), [
                SuiteGenerator.get_assertion(
                    "{0} = 1".format(case_count),
                    'case_autoload.{0}.case_missing'.format(auto_select.mode)
                )
            ]
        elif auto_select.mode == AUTO_SELECT_USERCASE:
            case = UserCaseXPath().case()
            return SessionDatum(
                id=action.case_session_var,
                function=case.slash('@case_id')
            ), [
                SuiteGenerator.get_assertion(
                    "{0} = 1".format(case.count()),
                    'case_autoload.{0}.case_missing'.format(auto_select.mode)
                )
            ]

    def configure_entry_advanced_form(self, module, e, form, **kwargs):
        def case_sharing_requires_assertion(form):
            actions = form.actions.open_cases
            for action in actions:
                if 'owner_id' in action.case_properties:
                    return True
            return False

        datums, assertions = self.get_datum_meta_assertions_advanced(module, form)
        datums.extend(SuiteGenerator.get_new_case_id_datums_meta(form))

        for datum_meta in datums:
            e.datums.append(datum_meta.datum)

        # assertions come after session
        e.assertions.extend(assertions)

        if self.app.case_sharing and case_sharing_requires_assertion(form):
            SuiteGenerator.add_case_sharing_assertion(e)

    def get_datum_meta_assertions_advanced(self, module, form):
        def get_target_module(case_type, module_id, with_product_details=False):
            if module_id:
                if module_id == module.unique_id:
                    return module

                from corehq.apps.app_manager.models import ModuleNotFoundException
                try:
                    target = module.get_app().get_module_by_unique_id(module_id)
                    if target.case_type != case_type:
                        raise ParentModuleReferenceError(
                            "Module with ID %s has incorrect case type" % module_id
                        )
                    if with_product_details and not hasattr(target, 'product_details'):
                        raise ParentModuleReferenceError(
                            "Module with ID %s has no product details configuration" % module_id
                        )
                    return target
                except ModuleNotFoundException as ex:
                    raise ParentModuleReferenceError(ex.message)
            else:
                if case_type == module.case_type:
                    return module

                target_modules = [
                    mod for mod in module.get_app().modules
                    if mod.case_type == case_type and (not with_product_details or hasattr(mod, 'product_details'))
                ]
                try:
                    return target_modules[0]
                except IndexError:
                    raise ParentModuleReferenceError(
                        "Module with case type %s in app %s not found" % (case_type, self.app)
                    )

        def get_manual_datum(action_, parent_filter_=''):
            target_module_ = get_target_module(action_.case_type, action_.details_module)
            referenced_by = form.actions.actions_meta_by_parent_tag.get(action_.case_tag)
            return SessionDatum(
                id=action_.case_session_var,
                nodeset=(SuiteGenerator.get_nodeset_xpath(action_.case_type, target_module_, True) +
                         parent_filter_),
                value="./@case_id",
                detail_select=self.get_detail_id_safe(target_module_, 'case_short'),
                detail_confirm=(
                    self.get_detail_id_safe(target_module_, 'case_long')
                    if not referenced_by or referenced_by['type'] != 'load' else None
                )
            )

        datums = []
        assertions = []
        for action in form.actions.get_load_update_actions():
            auto_select = action.auto_select
            if auto_select and auto_select.mode:
                datum, assertions = SuiteGenerator.get_auto_select_datums_and_assertions(action, auto_select, form)
                datums.append(FormDatumMeta(
                    datum=datum,
                    case_type=None,
                    requires_selection=False,
                    action=action
                ))
            else:
                if action.case_index.tag:
                    parent_action = form.actions.actions_meta_by_tag[action.case_index.tag]['action']
                    parent_filter = SuiteGenerator.get_parent_filter(
                        action.case_index.reference_id,
                        parent_action.case_session_var
                    )
                else:
                    parent_filter = ''
                datums.append(FormDatumMeta(
                    datum=get_manual_datum(action, parent_filter),
                    case_type=action.case_type,
                    requires_selection=True,
                    action=action
                ))

        if module.get_app().commtrack_enabled:
            try:
                last_action = list(form.actions.get_load_update_actions())[-1]
                if last_action.show_product_stock:
                    nodeset = ProductInstanceXpath().instance()
                    if last_action.product_program:
                        nodeset = nodeset.select('program_id', last_action.product_program)

                    target_module = get_target_module(last_action.case_type, last_action.details_module, True)

                    datums.append(FormDatumMeta(
                        datum=SessionDatum(
                            id='product_id',
                            nodeset=nodeset,
                            value="./@id",
                            detail_select=self.get_detail_id_safe(target_module, 'product_short')
                        ),
                        case_type=None,
                        requires_selection=True,
                        action=None
                    ))
            except IndexError:
                pass

        self.add_parent_datums(datums, module)

        return datums, assertions

    def add_parent_datums(self, datums, module):

        def update_refs(datum_meta, changed_ids_):
            """
            Update references in the nodeset of the given datum, if necessary

            e.g. "instance('casedb')/casedb/case[@case_type='guppy']
                                                [@status='open']
                                                [index/parent=instance('commcaresession')/session/data/parent_id]"
            is updated to
                 "instance('casedb')/casedb/case[@case_type='guppy']
                                                [@status='open']
                                                [index/parent=instance('commcaresession')/session/data/case_id]"
                                                                                                       ^^^^^^^
            because the case referred to by "parent_id" in the child module has the ID "case_id" in the parent
            module.
            """
            def _apply_change_to_datum_attr(datum, attr, change):
                xpath = getattr(datum, attr, None)
                if xpath:
                    old = session_var(change['old_id'])
                    new = session_var(change['new_id'])
                    setattr(datum, attr, xpath.replace(old, new))

            datum = datum_meta.datum
            action = datum_meta.action
            if action:
                if hasattr(action, 'case_indices'):
                    # This is an advanced module
                    for case_index in action.case_indices:
                        if case_index.tag in changed_ids_:
                            # update any reference to previously changed datums
                            for change in changed_ids_[case_index.tag]:
                                _apply_change_to_datum_attr(datum, 'nodeset', change)
                                _apply_change_to_datum_attr(datum, 'function', change)
                else:
                    if 'basic' in changed_ids_:
                        for change in changed_ids_['basic']:
                            _apply_change_to_datum_attr(datum, 'nodeset', change)
                            _apply_change_to_datum_attr(datum, 'function', change)

        def rename_other_id(this_datum_meta_, parent_datum_meta_, datum_ids_):
            """
            If the ID of parent datum matches the ID of another datum in this
            form, rename the ID of the other datum in this form

            e.g. if parent datum ID == "case_id" and there is a datum in this
            form with the ID of "case_id" too, then rename the ID of the datum
            in this form to "case_id_<case_type>" (where <case_type> is the
            case type of the datum in this form).
            """
            changed_id = {}
            parent_datum = parent_datum_meta_.datum
            action = this_datum_meta_.action
            if action:
                if parent_datum.id in datum_ids_:
                    datum = datum_ids_[parent_datum.id]
                    new_id = '_'.join((datum.datum.id, datum.case_type))
                    # Only advanced module actions have a case_tag attribute.
                    case_tag = getattr(action, 'case_tag', 'basic')
                    changed_id = {
                        case_tag: {
                            'old_id': datum.datum.id,
                            'new_id': new_id,
                        }
                    }
                    datum.datum.id = new_id
            return changed_id

        def get_changed_id(this_datum_meta_, parent_datum_meta_):
            """
            Maps IDs in the child module to IDs in the parent module

            e.g. The case with the ID "parent_id" in the child module has the
            ID "case_id" in the parent module.
            """
            changed_id = {}
            action = this_datum_meta_.action
            if action:
                case_tag = getattr(action, 'case_tag', 'basic')
                changed_id = {
                    case_tag: {
                        "old_id": this_datum_meta_.datum.id,
                        "new_id": parent_datum_meta_.datum.id
                    }
                }
            return changed_id

        def get_datums(module_):
            """
            Return the datums of the first form in the given module
            """
            datums_ = []
            if module_:
                try:
                    # assume that all forms in the module have the same case management
                    form = module_.get_form(0)
                except FormNotFoundException:
                    pass
                else:
                    datums_.extend(self.get_datums_meta_for_form_generic(form))

            return datums_

        def append_update(dict_, new_dict):
            for key in new_dict:
                dict_[key].append(new_dict[key])

        parent_datums = get_datums(module.root_module)
        if parent_datums:
            # we need to try and match the datums to the root module so that
            # the navigation on the phone works correctly
            # 1. Add in any datums that don't require user selection e.g. new case IDs
            # 2. Match the datum ID for datums that appear in the same position and
            #    will be loading the same case type
            # see advanced_app_features#child-modules in docs
            datum_ids = {d.datum.id: d for d in datums}
            index = 0
            changed_ids_by_case_tag = defaultdict(list)
            for this_datum_meta, parent_datum_meta in list(izip_longest(datums, parent_datums)):
                if not this_datum_meta:
                    continue
                update_refs(this_datum_meta, changed_ids_by_case_tag)
                if not parent_datum_meta:
                    continue
                if this_datum_meta.datum.id != parent_datum_meta.datum.id:
                    if not parent_datum_meta.requires_selection:
                        # Add parent datums of opened subcases and automatically-selected cases
                        datums.insert(index, parent_datum_meta)
                    elif this_datum_meta.case_type == parent_datum_meta.case_type:
                        append_update(changed_ids_by_case_tag,
                                      rename_other_id(this_datum_meta, parent_datum_meta, datum_ids))
                        append_update(changed_ids_by_case_tag,
                                      get_changed_id(this_datum_meta, parent_datum_meta))
                        this_datum_meta.datum.id = parent_datum_meta.datum.id
                index += 1

    def configure_entry_careplan_form(self, module, e, form=None, **kwargs):
            parent_module = self.app.get_module_by_unique_id(module.parent_select.module_id)
            e.datums.append(SessionDatum(
                id='case_id',
                nodeset=SuiteGenerator.get_nodeset_xpath(parent_module.case_type, parent_module, False),
                value="./@case_id",
                detail_select=self.get_detail_id_safe(parent_module, 'case_short'),
                detail_confirm=self.get_detail_id_safe(parent_module, 'case_long')
            ))

            def session_datum(datum_id, case_type, parent_ref, parent_val):
                nodeset = CaseTypeXpath(case_type).case().select(
                    'index/%s' % parent_ref, session_var(parent_val), quote=False
                ).select('@status', 'open')
                return SessionDatum(
                    id=datum_id,
                    nodeset=nodeset,
                    value="./@case_id",
                    detail_select=self.get_detail_id_safe(module, '%s_short' % case_type),
                    detail_confirm=self.get_detail_id_safe(module, '%s_long' % case_type)
                )

            e.stack = Stack()
            frame = CreateFrame()
            e.stack.add_frame(frame)
            if form.case_type == CAREPLAN_GOAL:
                if form.mode == 'create':
                    new_goal_id_var = 'case_id_goal_new'
                    e.datums.append(SessionDatum(id=new_goal_id_var, function='uuid()'))
                elif form.mode == 'update':
                    new_goal_id_var = 'case_id_goal'
                    e.datums.append(session_datum(new_goal_id_var, CAREPLAN_GOAL, 'parent', 'case_id'))

                if not module.display_separately:
                    open_goal = CaseIDXPath(session_var(new_goal_id_var)).case().select('@status', 'open')
                    frame.if_clause = '{count} = 1'.format(count=open_goal.count())
                    frame.add_command(XPath.string(id_strings.menu_id(parent_module)))
                    frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))
                    frame.add_command(XPath.string(id_strings.menu_id(module)))
                    frame.add_datum(StackDatum(id='case_id_goal', value=session_var(new_goal_id_var)))
                else:
                    frame.add_command(XPath.string(id_strings.menu_id(module)))
                    frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))

            elif form.case_type == CAREPLAN_TASK:
                if not module.display_separately:
                    frame.add_command(XPath.string(id_strings.menu_id(parent_module)))
                    frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))
                    frame.add_command(XPath.string(id_strings.menu_id(module)))
                    frame.add_datum(StackDatum(id='case_id_goal', value=session_var('case_id_goal')))
                    if form.mode == 'update':
                        count = CaseTypeXpath(CAREPLAN_TASK).case().select(
                            'index/goal', session_var('case_id_goal'), quote=False
                        ).select('@status', 'open').count()
                        frame.if_clause = '{count} >= 1'.format(count=count)

                        frame.add_command(XPath.string(
                            id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'update'))
                        ))
                else:
                    frame.add_command(XPath.string(id_strings.menu_id(module)))
                    frame.add_datum(StackDatum(id='case_id', value=session_var('case_id')))

                if form.mode == 'create':
                    e.datums.append(session_datum('case_id_goal', CAREPLAN_GOAL, 'parent', 'case_id'))
                elif form.mode == 'update':
                    e.datums.append(session_datum('case_id_goal', CAREPLAN_GOAL, 'parent', 'case_id'))
                    e.datums.append(session_datum('case_id_task', CAREPLAN_TASK, 'goal', 'case_id_goal'))

    def _schedule_filter_conditions(self, form, module, case):
        phase = form.get_phase()
        try:
            form_xpath = QualifiedScheduleFormXPath(form, phase, module, case_xpath=case)
            relevant = form_xpath.filter_condition(phase.id)
        except ScheduleError:
            relevant = None
        return relevant

    @property
    @memoized
    def menus(self):
        # avoid circular dependency
        from corehq.apps.app_manager.models import CareplanModule, AdvancedForm

        menus = []
        for module in self.modules:
            if isinstance(module, CareplanModule):
                update_menu = Menu(
                    id=id_strings.menu_id(module),
                    locale_id=id_strings.module_locale(module),
                )

                if not module.display_separately:
                    parent = self.app.get_module_by_unique_id(module.parent_select.module_id)
                    create_goal_form = module.get_form_by_type(CAREPLAN_GOAL, 'create')
                    create_menu = Menu(
                        id=id_strings.menu_id(parent),
                        locale_id=id_strings.module_locale(parent),
                    )
                    create_menu.commands.append(Command(id=id_strings.form_command(create_goal_form)))
                    menus.append(create_menu)

                    update_menu.root = id_strings.menu_id(parent)
                else:
                    update_menu.commands.extend([
                        Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'create'))),
                    ])

                update_menu.commands.extend([
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_GOAL, 'update'))),
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'create'))),
                    Command(id=id_strings.form_command(module.get_form_by_type(CAREPLAN_TASK, 'update'))),
                ])
                menus.append(update_menu)
            elif hasattr(module, 'get_menus'):
                for menu in module.get_menus():
                    menus.append(menu)
            else:
                menu_kwargs = {
                    'id': id_strings.menu_id(module),
                }
                if id_strings.menu_root(module):
                    menu_kwargs['root'] = id_strings.menu_root(module)

                if (self.app.domain and MODULE_FILTER.enabled(self.app.domain) and
                        self.app.enable_module_filtering and
                        getattr(module, 'module_filter', None)):
                    menu_kwargs['relevant'] = interpolate_xpath(module.module_filter)

                if self.app.enable_localized_menu_media:
                    menu_kwargs.update({
                        'menu_locale_id': id_strings.module_locale(module),
                        'media_image': bool(len(module.all_image_paths())),
                        'media_audio': bool(len(module.all_audio_paths())),
                        'image_locale_id': id_strings.module_icon_locale(module),
                        'audio_locale_id': id_strings.module_audio_locale(module),
                    })
                    menu = LocalizedMenu(**menu_kwargs)
                else:
                    menu_kwargs.update({
                        'locale_id': id_strings.module_locale(module),
                        'media_image': module.default_media_image,
                        'media_audio': module.default_media_audio,
                    })
                    menu = Menu(**menu_kwargs)

                def get_commands():
                    for form in module.get_forms():
                        command = Command(id=id_strings.form_command(form))

                        if form.requires_case():
                            form_datums = self.get_datums_meta_for_form_generic(form)
                            var_name = next(
                                meta.datum.id for meta in reversed(form_datums)
                                if meta.action and meta.requires_selection
                            )
                            case = CaseIDXPath(session_var(var_name)).case()
                        else:
                            case = None

                        if (
                            getattr(form, 'form_filter', None) and
                            not module.put_in_root and
                            (module.all_forms_require_a_case() or is_usercase_in_use(self.app.domain))
                        ):
                            command.relevant = interpolate_xpath(form.form_filter, case)

                        if getattr(module, 'has_schedule', False) and module.all_forms_require_a_case():
                            # If there is a schedule and another filter condition, disregard it...
                            # Other forms of filtering are disabled in the UI

                            schedule_filter_condition = self._schedule_filter_conditions(form, module, case)
                            if schedule_filter_condition is not None:
                                command.relevant = schedule_filter_condition

                        yield command

                    if hasattr(module, 'case_list') and module.case_list.show:
                        yield Command(id=id_strings.case_list_command(module))

                menu.commands.extend(get_commands())

                menus.append(menu)

        return menus

    @property
    def fixtures(self):
        return chain(self._case_sharing_fixtures, self._schedule_fixtures)

    @property
    def _case_sharing_fixtures(self):
        if self.app.case_sharing:
            f = Fixture(id='user-groups')
            f.user_id = 'demo_user'
            groups = etree.fromstring("""
                <groups>
                    <group id="demo_user_group_id">
                        <name>Demo Group</name>
                    </group>
                </groups>
            """)
            f.set_content(groups)
            yield f

    @property
    def _schedule_fixtures(self):
        schedule_modules = (module for module in self.modules
                            if getattr(module, 'has_schedule', False) and module.all_forms_require_a_case)
        schedule_phases = (phase for module in schedule_modules for phase in module.get_schedule_phases())
        schedule_forms = (form for phase in schedule_phases for form in phase.get_forms())

        for form in schedule_forms:
            schedule = form.schedule

            if schedule is None:
                raise (ScheduleError(_("There is no schedule for form {form_id}")
                                     .format(form_id=form.unique_id)))

            visits = [ScheduleFixtureVisit(id=visit.id,
                                           due=visit.due,
                                           starts=visit.starts,
                                           expires=visit.expires,
                                           repeats=visit.repeats,
                                           increment=visit.increment)
                      for visit in schedule.get_visits()]

            schedule_fixture = ScheduleFixture(
                id=id_strings.schedule_fixture(form.get_module(), form.get_phase(), form),
                schedule=Schedule(
                    starts=schedule.starts,
                    expires=schedule.expires if schedule.expires else '',
                    allow_unscheduled=schedule.allow_unscheduled,
                    visits=visits,
                )
            )
            yield schedule_fixture


class MediaSuiteGenerator(SuiteGeneratorBase):
    descriptor = u"Media Suite File"
    sections = ('media_resources',)

    @property
    def media_resources(self):
        PREFIX = 'jr://file/'
        # you have to call remove_unused_mappings
        # before iterating through multimedia_map
        self.app.remove_unused_mappings()
        if self.app.multimedia_map is None:
            self.app.multimedia_map = {}
        for path, m in self.app.multimedia_map.items():
            unchanged_path = path
            if path.startswith(PREFIX):
                path = path[len(PREFIX):]
            else:
                raise MediaResourceError('%s does not start with %s' % (path, PREFIX))
            path, name = split_path(path)
            # CommCare assumes jr://media/,
            # which is an alias to jr://file/commcare/media/
            # so we need to replace 'jr://file/' with '../../'
            # (this is a hack)
            install_path = u'../../{}'.format(path)
            local_path = u'./{}/{}'.format(path, name)

            if not getattr(m, 'unique_id', None):
                # lazy migration for adding unique_id to map_item
                m.unique_id = HQMediaMapItem.gen_unique_id(m.multimedia_id, unchanged_path)

            descriptor = None
            if self.app.build_version >= '2.9':
                type_mapping = {"CommCareImage": "Image",
                                "CommCareAudio": "Audio",
                                "CommCareVideo": "Video",
                                "CommCareMultimedia": "Text"}
                descriptor = u"{filetype} File: {name}".format(
                    filetype=type_mapping.get(m.media_type, "Media"),
                    name=name
                )

            yield MediaResource(
                id=id_strings.media_resource(m.unique_id, name),
                path=install_path,
                version=m.version,
                descriptor=descriptor,
                local=(local_path
                       if self.app.enable_local_resource
                       else None),
                remote=get_url_base() + reverse(
                    'hqmedia_download',
                    args=[m.media_type, m.multimedia_id]
                ) + urllib.quote(name.encode('utf-8')) if name else name
            )


def validate_suite(suite):
    if isinstance(suite, unicode):
        suite = suite.encode('utf8')
    if isinstance(suite, str):
        suite = etree.fromstring(suite)
    if isinstance(suite, etree._Element):
        suite = Suite(suite)
    assert isinstance(suite, Suite),\
        'Could not convert suite to a Suite XmlObject: %r' % suite

    def is_unique_list(things):
        return len(set(things)) == len(things)

    for detail in suite.details:
        orders = [field.sort_node.order for field in detail.fields
                  if field and field.sort_node]
        if not is_unique_list(orders):
            raise SuiteValidationError('field/sort/@order must be unique per detail')
