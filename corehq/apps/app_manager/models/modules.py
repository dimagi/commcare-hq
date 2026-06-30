import uuid
from collections import namedtuple
from copy import deepcopy

# FIXME(gettext_lazy): many of the gettext calls in this file can likely be
# changed to _ (gettext_lazy), but gettext is necessary for any value being
# used with jsonobject (which checks isinstance(value, str) at assignment).
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from memoized import memoized

from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DictProperty,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)
from dimagi.utils.web import parse_int

from corehq.apps.app_manager import (
    const,
    id_strings,
)
from corehq.apps.app_manager.exceptions import (
    FormNotFoundException,
    IncompatibleFormTypeException,
    ModuleNotFoundException,
    ScheduleError,
)
from corehq.apps.app_manager.helpers.validators import (
    AdvancedModuleValidator,
    ModuleBaseValidator,
    ModuleValidator,
    ReportModuleValidator,
    ShadowModuleValidator,
)
from corehq.apps.app_manager.suite_xml import xml_models as suite_models
from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RESULTS_INSTANCE,
)
from corehq.apps.app_manager.suite_xml.utils import get_select_chain
from corehq.apps.app_manager.templatetags.xforms_extras import (
    clean_trans,
)
from corehq.apps.app_manager.util import (
    module_offers_search,
    module_uses_inline_search,
)
from corehq.apps.app_manager.xpath import interpolate_xpath
from corehq.apps.hqmedia.models import ModuleMediaMixin
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError

from .base import (
    CustomAssertion,
    IndexedSchema,
    FormIdProperty,
    rename_key,
)
from .case_list import (
   DetailColumn,
   Detail,
   CaseList,
)
from .case_search import CaseSearch
from .form_actions import (
    AdvancedOpenCaseAction,
    CaseIndex,
    LoadUpdateAction,
)
from .forms import (
    AdvancedForm,
    Form,
    FormBase,
    FormSchedule,
    SchedulePhase,
    ShadowForm,
)
from .mixins import (
    CommentMixin,
    NavMenuItemMediaMixin,
)
from .report_app_config import ReportAppConfig


class ParentSelect(DocumentSchema):

    active = BooleanProperty(default=False)
    relationship = StringProperty(default='parent')
    module_id = StringProperty()


class FixtureSelect(DocumentSchema):
    """
    Configuration for creating a details screen from a fixture which can be used to pre-filter
    cases prior to displaying the case list.

    fixture_type:       LookupTable.tag
    display_column:     name of the column to display in the list
    localize:           boolean if display_column actually contains the key for the localized string
    variable_column:    name of the column whose value should be saved when the user selects an item
    xpath:              xpath expression to use as the case filter
    """
    active = BooleanProperty(default=False)
    fixture_type = StringProperty(exclude_if_none=True)
    display_column = StringProperty(exclude_if_none=True)
    localize = BooleanProperty(default=False)
    variable_column = StringProperty(exclude_if_none=True)
    xpath = StringProperty(default='', exclude_if_none=True)


class DetailPair(DocumentSchema):
    short = SchemaProperty(Detail)
    long = SchemaProperty(Detail)

    @classmethod
    def wrap(cls, data):
        self = super(DetailPair, cls).wrap(data)
        self.short.display = 'short'
        self.long.display = 'long'
        return self


class ShadowFormEndpoint(DocumentSchema):
    form_id = StringProperty()
    session_endpoint_id = StringProperty()

    def __eq__(self, other):
        if not isinstance(other, ShadowFormEndpoint):
            return False

        return self.form_id == other.form_id and self.session_endpoint_id == other.session_endpoint_id


class CaseListForm(NavMenuItemMediaMixin):
    form_id = FormIdProperty('modules[*].case_list_form.form_id')
    label = DictProperty()
    post_form_workflow = StringProperty(
        default=const.WORKFLOW_DEFAULT,
        choices=const.REGISTRATION_FORM_WORFLOWS,
    )
    relevancy_expression = StringProperty(exclude_if_none=True)

    def rename_lang(self, old_lang, new_lang):
        rename_key(self.label, old_lang, new_lang)

    def get_app(self):
        return self._module.get_app()


class ModuleBase(IndexedSchema, ModuleMediaMixin, NavMenuItemMediaMixin, CommentMixin):
    name = DictProperty(str)
    unique_id = StringProperty()
    case_type = StringProperty()
    case_list_form = SchemaProperty(CaseListForm)
    module_filter = StringProperty(exclude_if_none=True)
    put_in_root = BooleanProperty(default=False)
    root_module_id = StringProperty(exclude_if_none=True)
    fixture_select = SchemaProperty(FixtureSelect)
    report_context_tile = BooleanProperty(default=False)
    auto_select_case = BooleanProperty(default=False)
    is_training_module = BooleanProperty(default=False)
    session_endpoint_id = StringProperty(exclude_if_none=True)  # See toggles.SESSION_ENDPOINTS
    case_list_session_endpoint_id = StringProperty(exclude_if_none=True)
    custom_assertions = SchemaListProperty(CustomAssertion)

    def __init__(self, *args, **kwargs):
        super(ModuleBase, self).__init__(*args, **kwargs)
        self.assign_references()

    def __repr__(self):
        return f"{self.doc_type}(id='{self.id}', name='{self.default_name()}', unique_id='{self.unique_id}')"

    @property
    def is_surveys(self):
        return self.case_type == ""

    def assign_references(self):
        if hasattr(self, 'case_list'):
            self.case_list._module = self
        if hasattr(self, 'case_list_form'):
            self.case_list_form._module = self
        if hasattr(self, 'search_config'):
            self.search_config.title_label._module = self
            self.search_config.description._module = self

    @classmethod
    def wrap(cls, data):
        if cls is ModuleBase:
            doc_type = data['doc_type']
            if doc_type == 'Module':
                return Module.wrap(data)
            elif doc_type == 'AdvancedModule':
                return AdvancedModule.wrap(data)
            elif doc_type == 'ReportModule':
                return ReportModule.wrap(data)
            elif doc_type == 'ShadowModule':
                return ShadowModule.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for Module', doc_type)
        else:
            return super(ModuleBase, cls).wrap(data)

    def get_or_create_unique_id(self):
        """
        It is the caller's responsibility to save the Application
        after calling this function.

        WARNING: If called on the same doc in different requests without saving,
        this function will return a different uuid each time,
        likely causing unexpected behavior

        """
        if not self.unique_id:
            self.unique_id = uuid.uuid4().hex
        return self.unique_id

    get_forms = IndexedSchema.Getter('forms')

    def get_suite_forms(self):
        return [f for f in self.get_forms() if not f.is_a_disabled_release_form()]

    @parse_int([1])
    def get_form(self, i):

        try:
            return self.forms[i].with_id(i % len(self.forms), self)
        except IndexError:
            raise FormNotFoundException()

    def get_form_index(self, unique_id):
        for index, form in enumerate(self.get_forms()):
            if form.unique_id == unique_id:
                return index
        error = _("Could not find form with ID='{unique_id}' in module '{module_name}'.").format(
            module_name=self.name, unique_id=unique_id)
        raise FormNotFoundException(error)

    def get_child_modules(self):
        return [
            module for module in self.get_app().get_modules()
            if module.unique_id != self.unique_id and getattr(module, 'root_module_id', None) == self.unique_id
        ]

    @property
    def root_module(self):
        if self.root_module_id:
            return self._parent.get_module_by_unique_id(self.root_module_id,
                   error=_("Could not find parent menu for '{}'").format(self.default_name()))

    def requires_case_details(self):
        return False

    def root_requires_same_case(self):
        return self.root_module \
            and self.root_module.case_type == self.case_type \
            and self.root_module.all_forms_require_a_case()

    def get_case_types(self):
        return set([self.case_type])

    def get_app(self):
        return self._parent

    def is_multi_select(self):
        if hasattr(self, 'case_details'):
            return self.case_details.short.multi_select
        return False

    def is_auto_select(self):
        if self.is_multi_select and hasattr(self, 'case_details'):
            return self.case_details.short.auto_select
        return self.auto_select_case

    @property
    def max_select_value(self):
        return self.case_details.short.max_select_value

    def has_grouped_tiles(self):
        return (
            hasattr(self, 'case_details')
            and self.case_details.short.case_tile_template
            and self.case_details.short.case_tile_group.index_identifier
        )

    def default_name(self, app=None):
        if not app:
            app = self.get_app()
        return clean_trans(
            self.name,
            [app.default_language] + app.langs
        )

    def rename_lang(self, old_lang, new_lang):
        rename_key(self.name, old_lang, new_lang)
        for form in self.get_forms():
            form.rename_lang(old_lang, new_lang)
        for __, detail, __ in self.get_details():
            detail.rename_lang(old_lang, new_lang)

    def get_form_by_unique_id(self, unique_id):
        for form in self.get_forms():
            if form.get_unique_id() == unique_id:
                return form

    @property
    def validator(self):
        return ModuleBaseValidator(self)

    def validate_for_build(self):
        return self.validator.validate_for_build()

    @memoized
    def get_subcase_types(self):
        '''
        Return a set of each case type for which this module has a form that
        opens a new subcase of that type.
        '''
        subcase_types = set()
        for form in self.get_forms():
            if hasattr(form, 'get_subcase_types'):
                subcase_types.update(form.get_subcase_types())
        return subcase_types

    def get_custom_entries(self):
        """
        By default, suite entries are configured by forms, but you can also provide custom
        entries by overriding this function.

        See ReportModule for an example
        """
        return []

    def uses_media(self):
        """
        Whether the module uses media. If this returns false then media will not be generated
        for the module.
        """
        return True

    def uses_usercase(self):
        return False

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        raise IncompatibleFormTypeException()

    def user_deletable(self):
        """If the user can delete this module from the navmenu

        You cannot delete a shadow child menu whose parent is a shadow
        """
        source_module_id = getattr(self, 'source_module_id', False)
        if not source_module_id:
            return True

        root_module_id = getattr(self, 'root_module_id', False)
        if not root_module_id:
            return True

        app = self.get_app()
        parent_module = app.get_module_by_unique_id(root_module_id)

        if parent_module.module_type == 'shadow':
            return False

        return True


class ModuleDetailsMixin(object):
    @property
    def case_list_filter(self):
        try:
            return self.case_details.short.filter
        except AttributeError:
            return None

    @property
    def detail_sort_elements(self):
        try:
            return self.case_details.short.sort_elements
        except Exception:
            return []

    def search_detail(self, short_or_long):
        detail = deepcopy(getattr(self.case_details, short_or_long))
        detail.instance_name = RESULTS_INSTANCE
        return detail

    def rename_lang(self, old_lang, new_lang):
        super(Module, self).rename_lang(old_lang, new_lang)
        for case_list in (self.case_list, self.referral_list):
            case_list.rename_lang(old_lang, new_lang)

    @memoized
    def get_details(self):
        details = [
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('ref_short', self.ref_details.short, False),
            ('ref_long', self.ref_details.long, False),
        ]
        custom_detail = self.case_details.short.custom_xml
        if module_offers_search(self) and not (custom_detail or module_uses_inline_search(self)):
            details.append(('search_short', self.search_detail("short"), True))
            details.append(('search_long', self.search_detail("long"), True))
        return tuple(details)


class Module(ModuleBase, ModuleDetailsMixin):
    """
    A group of related forms, and configuration that applies to them all.
    Translates to a top-level menu on the phone.

    """
    module_type = 'basic'
    forms = SchemaListProperty(Form)
    case_details = SchemaProperty(DetailPair)
    ref_details = SchemaProperty(DetailPair)
    case_list = SchemaProperty(CaseList)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)
    parent_select = SchemaProperty(ParentSelect)
    search_config = SchemaProperty(CaseSearch)
    display_style = StringProperty(default='list')
    lazy_load_case_list_fields = BooleanProperty(default=False)
    show_case_list_optimization_options = BooleanProperty(default=False)

    @classmethod
    def new_module(cls, name, lang):
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): gettext("Name")},
                field='name',
                model='case',
                hasAutocomplete=True,
            )]
        )
        module = cls(
            name={(lang or 'en'): name or gettext("Untitled Menu")},
            forms=[],
            case_type='',
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
        )
        module.get_or_create_unique_id()
        return module

    @classmethod
    def new_training_module(cls, name, lang):
        module = cls.new_module(name, lang)
        module.is_training_module = True
        return module

    def new_form(self, name, lang, attachment=Ellipsis):
        from corehq.apps.app_manager.views.utils import get_blank_form_xml
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = Form(
            name={lang: name},
        )
        self.forms.append(form)
        form = self.get_form(-1)
        if attachment == Ellipsis:
            attachment = get_blank_form_xml(name)
        form.source = attachment
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, Form):
            new_form = form
        elif isinstance(form, AdvancedForm) and not len(list(form.actions.get_all_actions())):
            new_form = Form(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio
            )
            new_form._parent = self
            form._parent = self
            if with_source:
                new_form.source = form.source
        else:
            raise IncompatibleFormTypeException(_('''
                Cannot move an advanced form with actions into a basic menu.
            '''))

        if index is not None:
            self.forms.insert(index, new_form)
        else:
            self.forms.append(new_form)
        return self.get_form(index or -1)

    @property
    def validator(self):
        return ModuleValidator(self)

    def requires(self):
        r = set(["none"])
        for form in self.get_forms():
            r.add(form.requires)
        if self.case_list.show:
            r.add('case')
        if self.referral_list.show:
            r.add('referral')
        for val in ("referral", "case", "none"):
            if val in r:
                return val

    def requires_case_details(self):
        ret = False
        if self.case_list.show:
            return True
        for form in self.get_forms():
            if form.requires_case():
                ret = True
                break
        return ret

    @memoized
    def all_forms_require_a_case(self):
        return all([form.requires == 'case' for form in self.get_forms()])

    def uses_usercase(self):
        """Return True if this module has any forms that use the usercase.
        """
        return (self.case_type == const.USERCASE_TYPE
                or any(form.uses_usercase() for form in self.get_forms()))

    def grid_display_style(self):
        return self.display_style == 'grid'

    @property
    def additional_case_types(self):
        return self.search_config.additional_case_types


class AdvancedModule(ModuleBase):
    module_type = 'advanced'
    forms = SchemaListProperty(FormBase)
    case_details = SchemaProperty(DetailPair)
    product_details = SchemaProperty(DetailPair)
    case_list = SchemaProperty(CaseList)
    show_case_list_optimization_options = BooleanProperty(default=False)
    has_schedule = BooleanProperty()
    schedule_phases = SchemaListProperty(SchedulePhase)
    get_schedule_phases = IndexedSchema.Getter('schedule_phases')
    search_config = SchemaProperty(CaseSearch)

    @property
    def is_surveys(self):
        return False

    @classmethod
    def new_module(cls, name, lang):
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): gettext("Name")},
                field='name',
                model='case',
            )]
        )

        module = AdvancedModule(
            name={(lang or 'en'): name or gettext("Untitled Menu")},
            forms=[],
            case_type='',
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
            product_details=DetailPair(
                short=Detail(
                    columns=[
                        DetailColumn(
                            format='plain',
                            header={(lang or 'en'): gettext("Product")},
                            field='name',
                            model='product',
                        ),
                    ],
                ),
                long=Detail(),
            ),
        )
        module.get_or_create_unique_id()
        return module

    def new_form(self, name, lang, attachment=Ellipsis):
        from corehq.apps.app_manager.views.utils import get_blank_form_xml
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = AdvancedForm(
            name={lang: name},
        )
        form.schedule = FormSchedule(enabled=False)

        self.forms.append(form)
        form = self.get_form(-1)
        if attachment == Ellipsis:
            attachment = get_blank_form_xml(name)
        form.source = attachment
        return form

    def new_shadow_form(self, name, lang):
        lang = lang if lang else "en"
        name = name if name else _("Untitled Form")
        form = ShadowForm(
            name={lang: name},
        )
        form.schedule = FormSchedule(enabled=False)

        self.forms.append(form)
        form = self.get_form(-1)
        form.get_unique_id()  # This function sets the unique_id. Normally setting the source sets the id.
        return form

    def add_insert_form(self, from_module, form, index=None, with_source=False):
        if isinstance(form, AdvancedForm):
            new_form = form
        elif isinstance(form, Form):
            new_form = AdvancedForm(
                name=form.name,
                form_filter=form.form_filter,
                media_image=form.media_image,
                media_audio=form.media_audio,
                comment=form.comment,
            )
            new_form._parent = self
            form._parent = self
            if with_source:
                new_form.source = form.source
            actions = form.active_actions()
            open = actions.get('open_case', None)
            update = actions.get('update_case', None)
            close = actions.get('close_case', None)
            preload = actions.get('case_preload', None)
            subcases = actions.get('subcases', None)
            case_type = from_module.case_type

            base_action = None
            if open:
                base_action = AdvancedOpenCaseAction(
                    case_type=case_type,
                    case_tag='open_{0}_0'.format(case_type),
                    name_update=open.name_update,
                    open_condition=open.condition,
                    case_properties=update.update if update else {},
                )
                new_form.actions.open_cases.append(base_action)
            elif update or preload or close:
                base_action = LoadUpdateAction(
                    case_type=case_type,
                    case_tag='load_{0}_0'.format(case_type),
                    case_properties=update.update if update else {},
                    preload=preload.preload if preload else {}
                )

                if from_module.parent_select.active:
                    from_app = from_module.get_app()  # A form can be copied from a module in a different app.
                    select_chain = get_select_chain(from_app, from_module, include_self=False)
                    for n, link in enumerate(reversed(list(enumerate(select_chain)))):
                        i, module = link
                        new_form.actions.load_update_cases.append(LoadUpdateAction(
                            case_type=module.case_type,
                            case_tag='_'.join(['parent'] * (i + 1)),
                            details_module=module.unique_id,
                            case_index=CaseIndex(tag='_'.join(['parent'] * (i + 2)) if n > 0 else '')
                        ))

                    base_action.case_indices = [CaseIndex(tag='parent')]

                if close:
                    base_action.close_condition = close.condition
                new_form.actions.load_update_cases.append(base_action)

            if subcases:
                for i, subcase in enumerate(subcases):
                    open_subcase_action = AdvancedOpenCaseAction(
                        case_type=subcase.case_type,
                        case_tag='open_{0}_{1}'.format(subcase.case_type, i + 1),
                        name_update=subcase.name_update,
                        open_condition=subcase.condition,
                        case_properties=subcase.case_properties,
                        repeat_context=subcase.repeat_context,
                        case_indices=[CaseIndex(
                            tag=base_action.case_tag if base_action else '',
                            reference_id=subcase.reference_id,
                        )]
                    )
                    new_form.actions.open_cases.append(open_subcase_action)
        else:
            raise IncompatibleFormTypeException()

        if index is not None:
            self.forms.insert(index, new_form)
        else:
            self.forms.append(new_form)
        return self.get_form(index or -1)

    def rename_lang(self, old_lang, new_lang):
        super(AdvancedModule, self).rename_lang(old_lang, new_lang)
        self.case_list.rename_lang(old_lang, new_lang)

    def is_multi_select(self):
        return False

    def is_auto_select(self):
        return False

    def requires_case_details(self):
        if self.case_list.show:
            return True

        for form in self.get_forms():
            if any(action.case_type == self.case_type for action in form.actions.load_update_cases):
                return True

    def all_forms_require_a_case(self):
        return all(form.requires_case() for form in self.get_forms())

    def search_detail(self, short_or_long):
        detail = deepcopy(getattr(self.case_details, short_or_long))
        detail.instance_name = RESULTS_INSTANCE
        return detail

    @memoized
    def get_details(self):
        details = [
            ('case_short', self.case_details.short, True),
            ('case_long', self.case_details.long, True),
            ('product_short', self.product_details.short, self.get_app().commtrack_enabled),
            ('product_long', self.product_details.long, False),
        ]

        custom_detail = self.case_details.short.custom_xml
        if module_offers_search(self) and not (custom_detail or module_uses_inline_search(self)):
            details.append(('search_short', self.search_detail("short"), True))
            details.append(('search_long', self.search_detail("long"), True))
        return details

    @property
    def validator(self):
        return AdvancedModuleValidator(self)

    def _uses_case_type(self, case_type, invert_match=False):
        return any(form.uses_case_type(case_type, invert_match) for form in self.get_forms())

    def uses_usercase(self):
        """Return True if this module has any forms that use the usercase.
        """
        return self._uses_case_type(const.USERCASE_TYPE)

    @property
    def additional_case_types(self):
        return self.search_config.additional_case_types

    @property
    def phase_anchors(self):
        return [phase.anchor for phase in self.schedule_phases]

    def get_or_create_schedule_phase(self, anchor):
        """Returns a tuple of (phase, new?)"""
        if anchor is None or anchor.strip() == '':
            raise ScheduleError(_("You can't create a phase without an anchor property"))

        phase = next((phase for phase in self.get_schedule_phases() if phase.anchor == anchor), None)
        is_new_phase = False

        if phase is None:
            self.schedule_phases.append(SchedulePhase(anchor=anchor))
            # TODO: is there a better way of doing this?
            phase = list(self.get_schedule_phases())[-1]  # get the phase from the module so we know the _parent
            is_new_phase = True

        return (phase, is_new_phase)

    def _clear_schedule_phases(self):
        self.schedule_phases = []

    def update_schedule_phases(self, anchors):
        """ Take a list of anchors, reorders, deletes and creates phases from it """
        old_phases = {phase.anchor: phase for phase in self.get_schedule_phases()}
        self._clear_schedule_phases()

        for anchor in anchors:
            try:
                self.schedule_phases.append(old_phases.pop(anchor))
            except KeyError:
                self.get_or_create_schedule_phase(anchor)

        deleted_phases_with_forms = [anchor for anchor, phase in old_phases.items() if len(phase.forms)]
        if deleted_phases_with_forms:
            raise ScheduleError(_("You can't delete phases with anchors "
                                  "{phase_anchors} because they have forms attached to them").format(
                                      phase_anchors=(", ").join(deleted_phases_with_forms)))

        return self.get_schedule_phases()

    def update_schedule_phase_anchors(self, new_anchors):
        """ takes a list of tuples (id, new_anchor) and updates the phase anchors """
        for anchor in new_anchors:
            id = anchor[0] - 1
            new_anchor = anchor[1]
            try:
                list(self.get_schedule_phases())[id].change_anchor(new_anchor)
            except IndexError:
                pass  # That phase wasn't found, so we can't change it's anchor. Ignore it


class ReportModule(ModuleBase):
    """
    Module for user configurable reports
    """

    module_type = 'report'

    report_configs = SchemaListProperty(ReportAppConfig)
    forms = []
    _loaded = False
    put_in_root = False

    @property
    @memoized
    def reports(self):
        from corehq.apps.userreports.models import get_report_configs
        return get_report_configs([r.report_id for r in self.report_configs], self.get_app().domain)

    @classmethod
    def new_module(cls, name, lang):
        module = ReportModule(
            name={(lang or 'en'): name or gettext("Reports")},
            case_type='',
        )
        module.get_or_create_unique_id()
        return module

    @memoized
    def get_details(self):
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return list(ReportModuleSuiteHelper(self).get_details())

    def get_custom_entries(self):
        from corehq.apps.app_manager.suite_xml.features.mobile_ucr import ReportModuleSuiteHelper
        return ReportModuleSuiteHelper(self).get_custom_entries()

    def get_menus(self, build_profile_id=None):
        from corehq.apps.app_manager.suite_xml.utils import get_module_locale_id
        kwargs = {}
        if self.get_app().enable_module_filtering and self.module_filter:
            kwargs['relevant'] = interpolate_xpath(self.module_filter)

        menu = suite_models.LocalizedMenu(
            id=id_strings.menu_id(self),
            menu_locale_id=get_module_locale_id(self),
            media_image=self.uses_image(build_profile_id=build_profile_id),
            media_audio=self.uses_audio(build_profile_id=build_profile_id),
            image_locale_id=id_strings.module_icon_locale(self),
            audio_locale_id=id_strings.module_audio_locale(self),
            **kwargs
        )
        menu.commands.extend([
            suite_models.Command(id=id_strings.report_command(config.uuid))
            for config in self.report_configs
        ])
        yield menu

    def check_report_validity(self):
        """
        returns is_valid, valid_report_configs

        If any report doesn't exist, is_valid is False, otherwise True
        valid_report_configs is a list of all report configs that refer to existing reports

        """
        try:
            all_report_ids = [report._id for report in self.reports]
            valid_report_configs = [report_config for report_config in self.report_configs
                                    if report_config.report_id in all_report_ids]
            is_valid = (len(valid_report_configs) == len(self.report_configs))
        except ReportConfigurationNotFoundError:
            valid_report_configs = []  # assuming that if one report is in a different domain, they all are
            is_valid = False

        return namedtuple('ReportConfigValidity', 'is_valid valid_report_configs')(
            is_valid=is_valid,
            valid_report_configs=valid_report_configs
        )

    @property
    def validator(self):
        return ReportModuleValidator(self)


class ShadowModule(ModuleBase, ModuleDetailsMixin):
    """
    A module that acts as a shortcut to another module. This module has its own
    settings (name, icon/audio, filter, etc.) and its own case list/detail, but
    inherits case type and forms from its source module.
    """
    module_type = 'shadow'
    source_module_id = StringProperty()
    forms = []
    excluded_form_ids = SchemaListProperty()
    form_session_endpoints = SchemaListProperty(ShadowFormEndpoint)
    case_details = SchemaProperty(DetailPair)
    ref_details = SchemaProperty(DetailPair)
    case_list = SchemaProperty(CaseList)
    show_case_list_optimization_options = BooleanProperty(default=False)
    referral_list = SchemaProperty(CaseList)
    task_list = SchemaProperty(CaseList)
    parent_select = SchemaProperty(ParentSelect)
    search_config = SchemaProperty(CaseSearch)

    # Current allowed versions are '1' and '2'. version 1 had incorrect child
    # module behaviour, which was fixed for version 2. Apps in the wild were
    # depending on the old behaviour, so the new behaviour is applicable only
    # for new modules / apps.
    shadow_module_version = IntegerProperty(default=1)

    get_forms = IndexedSchema.Getter('forms')

    @property
    def source_module(self):
        if self.source_module_id:
            try:
                return self._parent.get_module_by_unique_id(self.source_module_id)
            except ModuleNotFoundException:
                pass
        return None

    @property
    def case_type(self):
        if not self.source_module:
            return None
        return self.source_module.case_type

    @property
    def additional_case_types(self):
        if not self.source_module:
            return []
        return self.source_module.additional_case_types

    @property
    def requires(self):
        if not self.source_module:
            return 'none'
        return self.source_module.requires

    _root_module_id = ModuleBase.root_module_id

    @property
    def root_module_id(self):
        if self.shadow_module_version == 1:
            if not self.source_module:
                return None
            return self.source_module.root_module_id

        return self._root_module_id

    @root_module_id.setter
    def root_module_id(self, value):
        if self.shadow_module_version == 1:
            raise AttributeError("Can't set root_module_id on modules with shadow_module_version = 1")
        else:
            self._root_module_id = value

    def get_suite_forms(self):
        if not self.source_module:
            return []
        return [f for f in self.source_module.get_forms() if f.unique_id not in self.excluded_form_ids]

    @parse_int([1])
    def get_form(self, i):
        return None

    def requires_case_details(self):
        if not self.source_module:
            return False
        return self.source_module.requires_case_details()

    def get_case_types(self):
        if not self.source_module:
            return []
        return self.source_module.get_case_types()

    @memoized
    def get_subcase_types(self):
        if not self.source_module:
            return []
        return self.source_module.get_subcase_types()

    @memoized
    def all_forms_require_a_case(self):
        if not self.source_module:
            return []
        return self.source_module.all_forms_require_a_case()

    def is_multi_select(self):
        if not self.source_module:
            return False
        return self.source_module.is_multi_select()

    def is_auto_select(self):
        if not self.source_module:
            return False
        return self.source_module.is_auto_select()

    @property
    def max_select_value(self):
        return self.source_module.max_select_value

    @classmethod
    def new_module(cls, name, lang, shadow_module_version=2):
        lang = lang or 'en'
        detail = Detail(
            columns=[DetailColumn(
                format='plain',
                header={(lang or 'en'): gettext("Name")},
                field='name',
                model='case',
            )]
        )
        module = ShadowModule(
            name={(lang or 'en'): name or gettext("Untitled Menu")},
            case_details=DetailPair(
                short=Detail(detail.to_json()),
                long=Detail(detail.to_json()),
            ),
            shadow_module_version=shadow_module_version,
        )
        module.get_or_create_unique_id()
        return module

    @property
    def validator(self):
        return ShadowModuleValidator(self)


# backwards compatibility with suite-1.0.xml
ModuleBase.get_locale_id = lambda self: id_strings.module_locale(self)

ModuleBase.get_case_list_command_id = lambda self: id_strings.case_list_command(self)
ModuleBase.get_case_list_locale_id = lambda self: id_strings.case_list_locale(self)

Module.get_referral_list_command_id = lambda self: id_strings.referral_list_command(self)
Module.get_referral_list_locale_id = lambda self: id_strings.referral_list_locale(self)
