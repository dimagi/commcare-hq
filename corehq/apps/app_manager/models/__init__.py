from django.utils.translation import gettext as _

from dimagi.ext.couchdbkit import (
    IntegerProperty,
    SchemaProperty,
    StringProperty,
)
from dimagi.utils.couch.undo import DeleteRecord

from corehq.apps.app_manager.templatetags.xforms_extras import (
    clean_trans,
)
from corehq.apps.cleanup.models import DeletedCouchDoc

from .applications import (  # noqa: F401
    Application,
    ApplicationBase,
    ApplicationReleaseLog,
    AppReleaseByLocation,
    BuildProfile,
    CredentialApplication,
    ExchangeApplication,
    ExchangeApplicationAdmin,
    GlobalAppConfig,
    LazyBlobDoc,
    LinkedApplication,
    RemoteApp,
    SavedAppBuild,
    absolute_url_property,
    import_app,
    validate_lang,
)
from .base import (  # noqa: F401
    Assertion,
    CustomAssertion,
    FormIdProperty,
    IndexedSchema,
    LabelProperty,
    form_id_references,
    rename_key,
)
from .case_list import (  # noqa: F401
    CaseList,
    CaseListLookupMixin,
    CaseTileGroupConfig,
    Detail,
    DetailColumn,
    DetailTab,
    GraphAnnotations,
    GraphConfiguration,
    GraphSeries,
    JRResourceProperty,
    MappingItem,
    SortElement,
)
from .case_search import (  # noqa: F401
    CaseSearch,
    CaseSearchCustomSortProperty,
    CaseSearchProperty,
    DefaultCaseSearchProperty,
    Itemset,
)
from .filters import (  # noqa: F401
    AncestorLocationTypeFilter,
    AutoFilter,
    AutoFilterConfig,
    CustomDataAutoFilter,
    CustomDatespanFilter,
    CustomMonthFilter,
    MobileFilterConfig,
    MobileSelectFilter,
    NumericFilter,
    ReportAppFilter,
    StaticChoiceFilter,
    StaticChoiceListFilter,
    StaticDatespanFilter,
    get_all_mobile_filter_configs,
    get_auto_filter_configurations,
    get_report_filter_class_for_doc_type,
)
from .form_actions import (  # noqa: F401
    AdvancedAction,
    AdvancedFormActions,
    AdvancedOpenCaseAction,
    ArbitraryDatum,
    AutoSelectCase,
    CaseIndex,
    CaseLoadReference,
    CaseReferences,
    CaseSaveReference,
    CaseSaveReferenceWithPath,
    ConditionalCaseUpdate,
    FormAction,
    FormActionCondition,
    FormActions,
    LoadCaseFromFixture,
    LoadUpdateAction,
    OpenCaseAction,
    OpenReferralAction,
    OpenSubCaseAction,
    PreloadAction,
    UpdateCaseAction,
    UpdateReferralAction,
)
from .forms import (  # noqa: F401
    AdvancedForm,
    CachedStringProperty,
    CustomInstance,
    Form,
    FormBase,
    FormDatum,
    FormLink,
    FormSchedule,
    FormSource,
    IndexedFormBase,
    SchedulePhase,
    SchedulePhaseForm,
    ScheduleVisit,
    ShadowForm,
)
from .mixins import (  # noqa: F401
    CommentMixin,
    CustomIcon,
    NavMenuItemMediaMixin,
)
from .modules import (  # noqa: F401
    AdvancedModule,
    CaseListForm,
    DetailPair,
    FixtureSelect,
    Module,
    ModuleBase,
    ModuleDetailsMixin,
    ParentSelect,
    ReportAppConfig,
    ReportModule,
    ShadowFormEndpoint,
    ShadowModule,
)


class DeleteApplicationRecord(DeleteRecord):

    app_id = StringProperty()

    def undo(self):
        app = ApplicationBase.get(self.app_id)
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        app.doc_type = app.get_doc_type()
        app.save(increment_version=False)


class DeleteModuleRecord(DeleteRecord):

    app_id = StringProperty()
    module_id = IntegerProperty()
    module = SchemaProperty(ModuleBase)

    def undo(self):
        app = Application.get(self.app_id)
        modules = app.modules
        modules.insert(self.module_id, self.module)
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        app.modules = modules
        app.save()


class DeleteFormRecord(DeleteRecord):

    app_id = StringProperty()
    module_id = IntegerProperty()
    module_unique_id = StringProperty()
    form_id = IntegerProperty()
    form = SchemaProperty(FormBase)

    def undo(self):
        app = Application.get(self.app_id)
        if self.module_unique_id is not None:
            name = clean_trans(self.form.name, app.default_language)
            module = app.get_module_by_unique_id(
                self.module_unique_id,
                error=_("Could not find form '{}'").format(name)
            )
        else:
            module = app.modules[self.module_id]
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        forms = module.forms
        forms.insert(self.form_id, self.form)
        module.forms = forms
        app.save()
