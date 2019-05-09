from __future__ import absolute_import
from __future__ import unicode_literals
import six
from collections import namedtuple, defaultdict
from six.moves import zip_longest

from django.utils.translation import ugettext as _
from corehq.apps.app_manager.suite_xml.contributors import SuiteContributorByModule

from corehq.apps.app_manager.suite_xml.utils import (
    get_select_chain_meta,
    get_form_enum_text,
    get_form_locale_id,
)
from corehq.apps.app_manager.exceptions import (
    ParentModuleReferenceError,
    SuiteValidationError)
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    USERCASE_ID, USERCASE_TYPE, )
from corehq.apps.app_manager.exceptions import FormNotFoundException
from corehq.apps.app_manager.util import actions_use_usercase
from corehq.apps.app_manager.xform import autoset_owner_id_for_open_case, \
    autoset_owner_id_for_subcase, autoset_owner_id_for_advanced_action
from corehq.apps.app_manager.xpath import CaseIDXPath, session_var, \
    ItemListFixtureXpath, XPath, ProductInstanceXpath, UserCaseXPath, \
    interpolate_xpath
from corehq.apps.app_manager.suite_xml.xml_models import *


class FormDatumMeta(namedtuple('FormDatumMeta', 'datum case_type requires_selection action from_parent')):
    def __new__(cls, datum, case_type, requires_selection, action, from_parent=False):
        """
        :param datum: The actual SessionDatum object
        :param case_type: The case type this datum represents
        :param requires_selection: True if this datum requires the user to make a selection
        :param action: The action that produced this datum
        :param from_parent: True if this datum is a placeholder necessary to match the parent module's session.
        """
        return super(FormDatumMeta, cls).__new__(cls, datum, case_type, requires_selection, action, from_parent)

    @property
    def is_new_case_id(self):
        return self.datum.function == 'uuid()'

    def __repr__(self):
        return 'FormDataumMeta(datum=<SessionDatum(id={})>, case_type={}, requires_selection={}, action={})'.format(
            self.datum.id, self.case_type, self.requires_selection, self.action
        )


class EntriesContributor(SuiteContributorByModule):
    def get_module_contributions(self, module):
        return self.entries_helper.entry_for_module(module)


class EntriesHelper(object):

    def __init__(self, app, modules=None, build_profile_id=None):
        from corehq.apps.app_manager.suite_xml.sections.details import DetailsHelper
        self.app = app
        self.modules = modules or list(app.get_modules())
        self.build_profile_id = build_profile_id
        self.details_helper = DetailsHelper(self.app, self.modules)

    def get_datums_meta_for_form_generic(self, form, module=None):
        if not module:
            module = form.get_module()
        if form.form_type == 'module_form':
            datums_meta = self.get_case_datums_basic_module(module, form)
        elif form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            datums_meta, _ = self.get_datum_meta_assertions_advanced(module, form)
            datums_meta.extend(EntriesHelper.get_new_case_id_datums_meta(form))
        else:
            raise SuiteValidationError("Unexpected form type '{}' with a case list form: {}".format(
                form.form_type, form.unique_id
            ))
        return datums_meta

    @staticmethod
    def get_filter_xpath(module, delegation=False):
        filter = module.case_details.short.filter
        if filter:
            xpath = '[%s]' % interpolate_xpath(filter)
        else:
            xpath = ''
        if delegation:
            xpath += "[index/parent/@case_type = '%s']" % module.case_type
            xpath += "[start_date = '' or double(date(start_date)) <= double(now())]"
        return xpath

    @staticmethod
    def get_nodeset_xpath(case_type, filter_xpath=''):
        return "instance('casedb')/casedb/case[@case_type='{case_type}'][@status='open']{filter_xpath}".format(
            case_type=case_type,
            filter_xpath=filter_xpath,
        )

    @staticmethod
    def get_parent_filter(relationship, parent_id):
        return "[index/{relationship}=instance('commcaresession')/session/data/{parent_id}]".format(
            relationship=relationship,
            parent_id=parent_id,
        )

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
            EntriesHelper.get_assertion(
                XPath.and_(base_xpath.count().eq(1),
                           xpath.count().eq(1)),
                'case_autoload.{0}.property_missing'.format(mode),
                [key],
            ),
            EntriesHelper.get_assertion(
                CaseIDXPath(xpath).case().count().eq(1),
                'case_autoload.{0}.case_missing'.format(mode),
            )
        ]
        return datum, assertions

    def entry_for_module(self, module):
        # avoid circular dependency
        from corehq.apps.app_manager.models import Module, AdvancedModule
        results = []
        for form in module.get_suite_forms():
            e = Entry()
            e.form = form.xmlns
            # Ideally all of this version check should happen in Command/Display class
            if self.app.enable_localized_menu_media:
                form_custom_icon = form.custom_icon
                e.command = LocalizedCommand(
                    id=id_strings.form_command(form, module),
                    menu_locale_id=get_form_locale_id(form),
                    menu_enum_text=get_form_enum_text(form),
                    media_image=form.uses_image(build_profile_id=self.build_profile_id),
                    media_audio=form.uses_audio(build_profile_id=self.build_profile_id),
                    image_locale_id=id_strings.form_icon_locale(form),
                    audio_locale_id=id_strings.form_audio_locale(form),
                    custom_icon_locale_id=(id_strings.form_custom_icon_locale(form, form_custom_icon.form)
                                           if form_custom_icon and not form_custom_icon.xpath else None),
                    custom_icon_form=(form_custom_icon.form if form_custom_icon else None),
                    custom_icon_xpath=(form_custom_icon.xpath
                                       if form_custom_icon and form_custom_icon.xpath else None),
                )
            else:
                e.command = Command(
                    id=id_strings.form_command(form, module),
                    locale_id=get_form_locale_id(form),
                    enum_text=get_form_enum_text(form),
                    media_image=form.default_media_image,
                    media_audio=form.default_media_audio,
                )
            config_entry = {
                'module_form': self.configure_entry_module_form,
                'advanced_form': self.configure_entry_advanced_form,
                'shadow_form': self.configure_entry_advanced_form,
            }[form.form_type]
            config_entry(module, e, form)

            if form.uses_usercase():
                EntriesHelper.add_usercase_id_assertion(e)

            EntriesHelper.add_custom_assertions(e, form)

            if (
                self.app.commtrack_enabled and
                session_var('supply_point_id') in getattr(form, 'source', "")
            ):
                from corehq.apps.app_manager.models import AUTO_SELECT_LOCATION
                datum, assertions = EntriesHelper.get_userdata_autoselect(
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
                    media_image=module.case_list.uses_image(build_profile_id=self.build_profile_id),
                    media_audio=module.case_list.uses_audio(build_profile_id=self.build_profile_id),
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
                for datum_meta in self.get_case_datums_basic_module(module):
                    e.datums.append(datum_meta.datum)
            elif isinstance(module, AdvancedModule):
                detail_inline = self.get_detail_inline_attr(module, module, "case_short")
                detail_confirm = None
                if not detail_inline:
                    detail_confirm = self.details_helper.get_detail_id_safe(module, 'case_long')
                e.datums.append(SessionDatum(
                    id='case_id_case_%s' % module.case_type,
                    nodeset=(EntriesHelper.get_nodeset_xpath(module.case_type)),
                    value="./@case_id",
                    detail_select=self.details_helper.get_detail_id_safe(module, 'case_short'),
                    detail_confirm=detail_confirm,
                    detail_persistent=self.get_detail_persistent_attr(module, module, "case_short"),
                    detail_inline=detail_inline,
                    autoselect=module.auto_select_case,
                ))
                if self.app.commtrack_enabled:
                    e.datums.append(SessionDatum(
                        id='product_id',
                        nodeset=ProductInstanceXpath().instance(),
                        value="./@id",
                        detail_select=self.details_helper.get_detail_id_safe(module, 'product_short')
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
        assertion = EntriesHelper.get_assertion("count(instance('groups')/groups/group) = 1",
                           'case_sharing.exactly_one_group')
        entry.assertions.append(assertion)

    @staticmethod
    def get_auto_select_assertions(case_id_xpath, mode, locale_arguments=None):
        case_count = CaseIDXPath(case_id_xpath).case().count()
        return [
            EntriesHelper.get_assertion(
                "{0} = 1".format(case_id_xpath.count()),
                'case_autoload.{0}.property_missing'.format(mode),
                locale_arguments
            ),
            EntriesHelper.get_assertion(
                "{0} = 1".format(case_count),
                'case_autoload.{0}.case_missing'.format(mode),
            )
        ]

    @staticmethod
    def add_custom_assertions(entry, form):
        for id, assertion in enumerate(form.custom_assertions):
            locale_id = id_strings.custom_assertion_locale(form.get_module(), form, id)
            entry.assertions.append(EntriesHelper.get_assertion(assertion.test, locale_id))

    @staticmethod
    def add_usercase_id_assertion(entry):
        assertion = EntriesHelper.get_assertion("count(instance('casedb')/casedb/case[@case_type='commcare-user']"
                                                "[hq_user_id=instance('commcaresession')/session/context/userid])"
                                                " = 1", "case_autoload.usercase.case_missing")
        entry.assertions.append(assertion)

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
                    # see XForm._create_casexml_2
                    if not subcase.repeat_context:
                        datums.append(FormDatumMeta(
                            datum=SessionDatum(
                                id=form.session_var_for_action(subcase), function='uuid()'
                            ),
                            case_type=subcase.case_type,
                            requires_selection=False,
                            action=subcase
                        ))
        elif form.form_type == 'advanced_form' or form.form_type == "shadow_form":
            for action in form.actions.get_open_actions():
                if not action.repeat_context:
                    datums.append(FormDatumMeta(
                        datum=SessionDatum(id=action.case_session_var, function='uuid()'),
                        case_type=action.case_type,
                        requires_selection=False,
                        action=action
                    ))

        return datums

    def get_case_datums_basic_module(self, module, form=None):
        datums = []
        if not form or form.requires_case():
            datums.extend(self.get_datum_meta_module(module, use_filter=True))

        if form:
            datums.extend(EntriesHelper.get_new_case_id_datums_meta(form))
            datums.extend(EntriesHelper.get_extra_case_id_datums(form))

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
            EntriesHelper.add_case_sharing_assertion(e)

    def get_datum_meta_module(self, module, use_filter=False):
        datums = []
        datum_module = module.source_module if module.module_type == 'shadow' else module
        datums_meta = get_select_chain_meta(self.app, datum_module)
        for i, datum in enumerate(datums_meta):
            # get the session var for the previous datum if there is one
            parent_id = datums_meta[i - 1]['session_var'] if i >= 1 else ''
            if parent_id:
                parent_filter = EntriesHelper.get_parent_filter(
                    datum['module'].parent_select.relationship, parent_id
                )
            else:
                parent_filter = ''

            # Figure out which module will supply the details (select, confirm, etc.)
            # for this datum. Normally this is the datum's own module.
            detail_module = datum['module']

            # Shadow modules are different because datums_meta is generated based on the source module,
            # but the various details should be supplied based on the shadow's own configuration.
            if module.module_type == 'shadow':
                if datum['module'].unique_id == module.source_module_id:
                    # We're looking at the datum that corresponds to the original module,
                    # so use that module for details
                    detail_module = module
                else:
                    # Check for case list parent child selection. If both shadow and source use parent case
                    # selection, datums_meta will contain a datum for the parent case, based on the SOURCE's
                    # parent select, and when we see that datum, we need to use the SHADOW's parent select
                    # to supply the details.
                    shadow_active = hasattr(module, 'parent_select') and module.parent_select.active
                    source_active = hasattr(datum_module, 'parent_select') and datum_module.parent_select.active
                    if shadow_active and source_active:
                        if datum['module'].unique_id == datum_module.parent_select.module_id:
                            detail_module = self.app.get_module_by_unique_id(module.parent_select.module_id)

            detail_persistent = self.get_detail_persistent_attr(datum['module'], detail_module, "case_short")
            detail_inline = self.get_detail_inline_attr(datum['module'], detail_module, "case_short")

            fixture_select_filter = ''
            if datum['module'].fixture_select.active:
                datums.append(FormDatumMeta(
                    datum=SessionDatum(
                        id=id_strings.fixture_session_var(datum['module']),
                        nodeset=ItemListFixtureXpath(datum['module'].fixture_select.fixture_type).instance(),
                        value=datum['module'].fixture_select.variable_column,
                        detail_select=id_strings.fixture_detail(detail_module)
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

            filter_xpath = EntriesHelper.get_filter_xpath(detail_module) if use_filter else ''

            datums.append(FormDatumMeta(
                datum=SessionDatum(
                    id=datum['session_var'],
                    nodeset=(EntriesHelper.get_nodeset_xpath(datum['case_type'], filter_xpath=filter_xpath)
                             + parent_filter + fixture_select_filter),
                    value="./@case_id",
                    detail_select=self.details_helper.get_detail_id_safe(detail_module, 'case_short'),
                    detail_confirm=(
                        self.details_helper.get_detail_id_safe(detail_module, 'case_long')
                        if datum['index'] == 0 and not detail_inline else None
                    ),
                    detail_persistent=detail_persistent,
                    detail_inline=detail_inline,
                    autoselect=datum['module'].auto_select_case,
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
            return EntriesHelper.get_userdata_autoselect(
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
            assertions = EntriesHelper.get_auto_select_assertions(xpath, auto_select.mode, [auto_select.value_key])
            return SessionDatum(
                id=action.case_session_var,
                function=xpath
            ), assertions
        elif auto_select.mode == AUTO_SELECT_FIXTURE:
            xpath_base = ItemListFixtureXpath(auto_select.value_source).instance()
            xpath = xpath_base.slash(auto_select.value_key)
            fixture_assertion = EntriesHelper.get_assertion(
                "{0} = 1".format(xpath_base.count()),
                'case_autoload.{0}.exactly_one_fixture'.format(auto_select.mode),
                [auto_select.value_source]
            )
            assertions = EntriesHelper.get_auto_select_assertions(xpath, auto_select.mode, [auto_select.value_key])
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
                EntriesHelper.get_assertion(
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
                EntriesHelper.get_assertion(
                    "{0} = 1".format(case.count()),
                    'case_autoload.{0}.case_missing'.format(auto_select.mode)
                )
            ]

    def get_load_case_from_fixture_datums(self, action, target_module, form):
        datums = []
        load_case_from_fixture = action.load_case_from_fixture

        if (load_case_from_fixture.arbitrary_datum_id and
                load_case_from_fixture.arbitrary_datum_function):
            datums.append(FormDatumMeta(
                SessionDatum(
                    id=load_case_from_fixture.arbitrary_datum_id,
                    function=load_case_from_fixture.arbitrary_datum_function,
                ),
                case_type=action.case_type,
                requires_selection=True,
                action=action,
            ))
        datums.append(FormDatumMeta(
            datum=SessionDatum(
                id=load_case_from_fixture.fixture_tag,
                nodeset=load_case_from_fixture.fixture_nodeset,
                value=load_case_from_fixture.fixture_variable,
                detail_select=self.details_helper.get_detail_id_safe(target_module, 'case_short'),
                detail_confirm=self.details_helper.get_detail_id_safe(target_module, 'case_long'),
                autoselect=load_case_from_fixture.auto_select_fixture,
            ),
            case_type=action.case_type,
            requires_selection=True,
            action=action,
        ))

        if action.case_tag:
            if action.case_index.tag:
                parent_action = form.actions.actions_meta_by_tag[action.case_index.tag]['action']
                parent_filter = EntriesHelper.get_parent_filter(
                    action.case_index.reference_id,
                    parent_action.case_session_var
                )
            else:
                parent_filter = ''
            session_var_for_fixture = session_var(load_case_from_fixture.fixture_tag)
            filter_for_casedb = '[{0}={1}]'.format(load_case_from_fixture.case_property, session_var_for_fixture)
            nodeset = EntriesHelper.get_nodeset_xpath(action.case_type, filter_xpath=filter_for_casedb)
            nodeset += parent_filter

            datums.append(FormDatumMeta(
                datum=SessionDatum(
                    id=action.case_tag,
                    nodeset=nodeset,
                    value="./@case_id",
                    autoselect=load_case_from_fixture.auto_select,
                ),
                case_type=action.case_type,
                requires_selection=False,
                action=action,
            ))

        return datums

    def configure_entry_advanced_form(self, module, e, form, **kwargs):
        def case_sharing_requires_assertion(form):
            actions = form.actions.open_cases
            for action in actions:
                if autoset_owner_id_for_advanced_action(action):
                    return True
            return False

        datums, assertions = self.get_datum_meta_assertions_advanced(module, form)
        datums.extend(EntriesHelper.get_new_case_id_datums_meta(form))

        for datum_meta in datums:
            e.datums.append(datum_meta.datum)

        # assertions come after session
        e.assertions.extend(assertions)

        if self.app.case_sharing and case_sharing_requires_assertion(form):
            EntriesHelper.add_case_sharing_assertion(e)

    def get_datum_meta_assertions_advanced(self, module, form):
        def get_target_module(case_type, module_id, with_product_details=False):
            if module_id:
                if module_id == module.unique_id:
                    return module

                from corehq.apps.app_manager.models import ModuleNotFoundException
                try:
                    target = module.get_app().get_module_by_unique_id(module_id,
                             error=_("Could not find target module used by form '{}'").format(form.default_name()))
                    if target.case_type != case_type:
                        raise ParentModuleReferenceError(
                            _(
                                "Form '%(form_name)s' in module '%(module_name)s' "
                                "references a module with an incorrect case type: "
                                "module '%(target_name)s' expected '%(expected_case_type)s', "
                                "found '%(target_case_type)s'"
                            ) % {
                                'form_name': form.default_name(),
                                'module_name': module.default_name(),
                                'target_name': target.default_name(),
                                'expected_case_type': case_type,
                                'target_case_type': target.case_type,
                            }
                        )
                    if with_product_details and not hasattr(target, 'product_details'):
                        raise ParentModuleReferenceError(
                            "Module with ID %s has no product details configuration" % module_id
                        )
                    return target
                except ModuleNotFoundException as e:
                    raise ParentModuleReferenceError(six.text_type(e))
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
            filter_xpath = EntriesHelper.get_filter_xpath(target_module_)
            detail_inline = self.get_detail_inline_attr(target_module_, target_module_, "case_short")

            return SessionDatum(
                id=action_.case_session_var,
                nodeset=(EntriesHelper.get_nodeset_xpath(action_.case_type, filter_xpath=filter_xpath)
                         + parent_filter_),
                value="./@case_id",
                detail_select=self.details_helper.get_detail_id_safe(target_module_, 'case_short'),
                detail_confirm=(
                    self.details_helper.get_detail_id_safe(target_module_, 'case_long')
                    if (not referenced_by or referenced_by['type'] != 'load') and not detail_inline else None
                ),
                detail_persistent=self.get_detail_persistent_attr(target_module_, target_module_, "case_short"),
                detail_inline=detail_inline,
                autoselect=target_module_.auto_select_case,
            )

        datums = []
        assertions = []
        for action in form.actions.get_load_update_actions():
            auto_select = action.auto_select
            load_case_from_fixture = action.load_case_from_fixture
            if auto_select and auto_select.mode:
                datum, assertions = EntriesHelper.get_auto_select_datums_and_assertions(action, auto_select, form)
                datums.append(FormDatumMeta(
                    datum=datum,
                    case_type=None,
                    requires_selection=False,
                    action=action
                ))
            elif load_case_from_fixture:
                target_module = get_target_module(action.case_type, action.details_module)
                datums.extend(self.get_load_case_from_fixture_datums(action, target_module, form))
            else:
                if action.case_index.tag:
                    parent_action = form.actions.actions_meta_by_tag[action.case_index.tag]['action']
                    parent_filter = EntriesHelper.get_parent_filter(
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
                            detail_select=self.details_helper.get_detail_id_safe(target_module, 'product_short'),
                            detail_persistent=self.get_detail_persistent_attr(
                                target_module, target_module, "product_short"
                            ),
                            detail_inline=self.get_detail_inline_attr(
                                target_module, target_module, "product_short"
                            ),
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
            for this_datum_meta, parent_datum_meta in list(zip_longest(datums, parent_datums)):
                if this_datum_meta:
                    update_refs(this_datum_meta, changed_ids_by_case_tag)
                if not parent_datum_meta:
                    continue
                if not this_datum_meta or this_datum_meta.datum.id != parent_datum_meta.datum.id:
                    if not parent_datum_meta.requires_selection:
                        # Add parent datums of opened subcases and automatically-selected cases
                        datums.insert(index, parent_datum_meta._replace(from_parent=True))
                    elif this_datum_meta and this_datum_meta.case_type == parent_datum_meta.case_type:
                        append_update(changed_ids_by_case_tag,
                                      rename_other_id(this_datum_meta, parent_datum_meta, datum_ids))
                        append_update(changed_ids_by_case_tag,
                                      get_changed_id(this_datum_meta, parent_datum_meta))
                        this_datum_meta.datum.id = parent_datum_meta.datum.id
                index += 1

    @staticmethod
    def _get_module_for_persistent_context(detail_module, module_unique_id):
        module_for_persistent_context = detail_module.get_app().get_module_by_unique_id(module_unique_id)
        if (module_for_persistent_context and
                (module_for_persistent_context.case_details.short.use_case_tiles or
                 module_for_persistent_context.case_details.short.custom_xml
                 )):
            return module_for_persistent_context

    def get_detail_persistent_attr(self, module, detail_module, detail_type="case_short"):
        detail, detail_enabled = self._get_detail_from_module(module, detail_type)
        if detail_enabled:
            # if configured to use persisted case tile context from another module which has case tiles
            # configured then get id_string for that module
            if detail.persistent_case_tile_from_module:
                module_for_persistent_context = self._get_module_for_persistent_context(
                    module, detail.persistent_case_tile_from_module
                )
                if module_for_persistent_context:
                    return id_strings.detail(module_for_persistent_context, detail_type)
            if self._has_persistent_tile(detail):
                return id_strings.detail(detail_module, detail_type)
            if detail.persist_case_context and detail_type == "case_short":
                # persistent_case_context will not work on product lists.
                return id_strings.persistent_case_context_detail(detail_module)
        return None

    def _get_detail_inline_attr_from_module(self, module, module_unique_id):
        module_for_persistent_context = self._get_module_for_persistent_context(module, module_unique_id)
        if module_for_persistent_context:
            return self.details_helper.get_detail_id_safe(module_for_persistent_context, "case_long")

    def get_detail_inline_attr(self, module, detail_module, detail_type="case_short"):
        assert detail_type in ["case_short", "product_short"]
        detail, detail_enabled = self._get_detail_from_module(module, detail_type)
        if detail_enabled and detail.pull_down_tile:
            if detail_type == "case_short" and detail.persistent_case_tile_from_module:
                inline_attr = self._get_detail_inline_attr_from_module(
                    module, detail.persistent_case_tile_from_module)
                if inline_attr:
                    return inline_attr
            if self._has_persistent_tile(detail):
                list_type = "case_long" if detail_type == "case_short" else "product_long"
                return self.details_helper.get_detail_id_safe(detail_module, list_type)
        return None

    def _get_detail_from_module(self, module, detail_type):
        """
        Return the Detail object of the given type from the given module
        """
        details = {d[0]: d for d in module.get_details()}
        _, detail, detail_enabled = details[detail_type]
        return detail, detail_enabled

    def _has_persistent_tile(self, detail):
        """
        Return True if the given Detail is configured to persist a case tile on forms
        """
        return detail.persist_tile_on_forms and (detail.use_case_tiles or detail.custom_xml)
