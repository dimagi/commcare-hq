import json
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_enabled
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege
from corehq import privileges
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.reports.dbaccessors import touch_exports
from corehq.apps.reports.standard import export
from corehq.apps.reports.models import FormExportSchema, HQGroupExportConfiguration, CaseExportSchema
from corehq.apps.reports.standard.export import DeidExportReport
from couchexport.models import ExportTable, ExportSchema, ExportColumn, display_column_types, SplitColumn
from django.utils.translation import ugettext as _, ugettext_lazy
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.commtrack.models import StockExportColumn
from corehq.apps.domain.models import Domain


USERNAME_TRANSFORM = 'corehq.apps.export.transforms.user_id_to_username'
OWNERNAME_TRANSFORM = 'corehq.apps.export.transforms.owner_id_to_display'
CASENAME_TRANSFORM = 'corehq.apps.export.transforms.case_id_to_case_name'

FORM_CASE_ID_PATH = 'form.case.@case_id'


class AbstractProperty(object):
    def __get__(self, instance, owner):
        raise NotImplementedError()


class DEID(object):
    options = (
        ('', ''),
        (ugettext_lazy('Sensitive ID'), 'couchexport.deid.deid_ID'),
        (ugettext_lazy('Sensitive Date'), 'couchexport.deid.deid_date'),
    )
    json_options = [{'label': label, 'value': value}
                    for label, value in options]


class ColumnTypesOptions(object):
    json_options = [
        {'label': meta.label, 'value': value}
        for value, meta in display_column_types.items() if meta.label
    ]


class CustomExportHelper(object):

    ExportSchemaClass = AbstractProperty()
    ExportReport = AbstractProperty()
    export_title = AbstractProperty()

    allow_deid = False
    allow_repeats = True

    export_type = 'form'

    @property
    def default_order(self):
        return {}

    def update_custom_params(self):
        if len(self.custom_export.tables) > 0:
            if self.export_stock:
                self.custom_export.tables[0].columns.append(
                    StockExportColumn(domain=self.domain, index='_id')
                )

    def format_config_for_javascript(self, table_configuration):
        return table_configuration

    def has_stock_column(self):
        return any(
            col.doc_type == 'StockExportColumn'
            for col in self.custom_export.tables[0].columns
        ) if self.custom_export.tables else False

    def __init__(self, request, domain, export_id=None, minimal=False):
        self.request = request
        self.domain = domain
        self.presave = False
        self.transform_dates = False
        self.creating_new_export = not bool(export_id)
        self.minimal = minimal

        if export_id:
            self.custom_export = self.ExportSchemaClass.get(export_id)
            # also update the schema to include potential new stuff
            self.custom_export.update_schema()

            # enable configuring saved exports from this page
            saved_group = HQGroupExportConfiguration.get_for_domain(self.domain)
            self.presave = export_id in saved_group.custom_export_ids

            self.export_stock = self.has_stock_column()

            try:
                assert self.custom_export.doc_type == 'SavedExportSchema', 'bad export doc type'
                assert self.custom_export.type == self.export_type, 'wrong export type specified'
                assert self.custom_export.index[0] == domain, 'bad export doc domain'
            except AssertionError, e:
                raise BadExportConfiguration(str(e))
        else:
            self.custom_export = self.ExportSchemaClass(type=self.export_type)
            self.export_stock = False

    @property
    @memoized
    def post_data(self):
        return json.loads(self.request.body)

    def update_custom_export(self):
        """
        Updates custom_export object from the request
        and saves to the db
        """

        post_data = self.post_data

        custom_export_json = post_data['custom_export']

        SAFE_KEYS = ('default_format', 'is_safe', 'name', 'schema_id', 'transform_dates')
        for key in SAFE_KEYS:
            self.custom_export[key] = custom_export_json[key]

        # update the custom export index (to stay in sync)
        schema_id = self.custom_export.schema_id
        schema = ExportSchema.get(schema_id)
        self.custom_export.index = schema.index
        self.presave = post_data['presave']
        self.export_stock = post_data['export_stock']

        self.custom_export.tables = [
            ExportTable.wrap(table)
            for table in custom_export_json['tables']
        ]

        table_dict = dict((t.index, t) for t in self.custom_export.tables)
        for table in self.custom_export.tables:
            if table.index in table_dict:
                table_dict[table.index].columns = table.columns
            else:
                self.custom_export.tables.append(
                    ExportTable(
                        index=table.index,
                        display=self.custom_export.name,
                        columns=table.columns
                    )
                )

        self.update_custom_params()
        self.custom_export.custom_validate()
        self.custom_export.save()
        touch_exports(self.domain)

        if self.presave:
            HQGroupExportConfiguration.add_custom_export(self.domain, self.custom_export.get_id)
        else:
            HQGroupExportConfiguration.remove_custom_export(self.domain, self.custom_export.get_id)
        return self.custom_export.get_id

    def get_context(self):
        table_configuration = self.format_config_for_javascript(self.custom_export.table_configuration)
        if self.minimal:
            table_configuration = filter(lambda t: t['selected'], table_configuration)
        return {
            'custom_export': self.custom_export,
            'default_order': self.default_order,
            'deid_options': DEID.json_options,
            'column_type_options': ColumnTypesOptions.json_options,
            'presave': self.presave,
            'export_stock': self.export_stock,
            'DeidExportReport_name': DeidExportReport.name,
            'table_configuration': table_configuration,
            'domain': self.domain,
            'commtrack_domain': Domain.get_by_name(self.domain).commtrack_enabled,
            'minimal': self.minimal,
            'helper': {
                'back_url': self.ExportReport.get_url(domain=self.domain),
                'export_title': self.export_title,
                'slug': self.ExportReport.slug,
                'allow_deid': self.allow_deid,
                'allow_repeats': self.allow_repeats
            }
        }


class FormCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = FormExportSchema
    ExportReport = export.ExcelExportReport

    allow_repeats = True

    default_questions = [FORM_CASE_ID_PATH, "form.meta.timeEnd", "_id", "id", "form.meta.username"]
    questions_to_show = default_questions + ["form.meta.timeStart", "received_on", "form.meta.location.#text"]

    @property
    def export_title(self):
        return _('Export Submissions to Excel')

    def __init__(self, request, domain, export_id=None, minimal=False):
        super(FormCustomExportHelper, self).__init__(request, domain, export_id, minimal)
        if not self.custom_export.app_id:
            self.custom_export.app_id = request.GET.get('app_id')

    @property
    def allow_deid(self):
        return has_privilege(self.request, privileges.DEIDENTIFIED_DATA)

    def update_custom_params(self):
        p = self.post_data['custom_export']
        e = self.custom_export
        e.include_errors = p['include_errors']
        e.split_multiselects = p['split_multiselects']
        e.app_id = p['app_id']

        super(FormCustomExportHelper, self).update_custom_params()

    @property
    @memoized
    def default_order(self):
        return self.custom_export.get_default_order()

    def update_table_conf_with_questions(self, table_conf):
        column_conf = table_conf[0].get("column_configuration", [])

        current_questions = set(self.custom_export.question_order)
        remaining_questions = current_questions.copy()

        def is_special_type(q):
            return any([q.startswith('form.#'), q.startswith('form.@'), q.startswith('form.case.'),
                        q.startswith('form.meta.'), q.startswith('form.subcase_')])

        def generate_additional_columns(requires_case):
            ret = []
            case_name_col = CustomColumn(slug='case_name', index=FORM_CASE_ID_PATH, display='info.case_name',
                                         transform=CASENAME_TRANSFORM, show=True, selected=True)
            if not requires_case:
                case_name_col.show, case_name_col.selected, case_name_col.tag = False, False, 'deleted'
            matches = filter(case_name_col.match, column_conf)
            if matches:
                # hack/annoying - also might have to re-add the case id column which can get
                # overwritten by case name if only that is set.
                case_id_cols = filter(lambda col: col['index'] == FORM_CASE_ID_PATH, column_conf)
                if len(case_id_cols) <= 1:
                    ret.append(ExportColumn(
                        index=FORM_CASE_ID_PATH,
                        display='info.case_id',
                        show=True,
                    ).to_config_format(selected=False))

                for match in matches:
                    case_name_col.format_for_javascript(match)

            elif filter(lambda col: col["index"] == case_name_col.index, column_conf):
                ret.append(case_name_col.default_column())
            return ret

        question_schema = self.custom_export.question_schema.question_schema

        def update_multi_select_column(question, col):
            if question in question_schema and not question_schema[question].repeat_context:
                if self.creating_new_export:
                    col["options"] = question_schema[question].options
                    col["allOptions"] = question_schema[question].options
                    col["doc_type"] = SplitColumn.__name__
                else:
                    current_options = set(col.get("options", []))
                    col["allOptions"] = list(set(question_schema[question].options) | current_options)

        for col in column_conf:
            question = col["index"]
            if question in remaining_questions:
                remaining_questions.discard(question)
                col["show"] = True
            if question.startswith("form.") and not is_special_type(question) and question not in current_questions:
                col["tag"] = "deleted"
                col["show"] = False
            if question in self.questions_to_show:
                col["show"] = True
            if self.creating_new_export and (question in self.default_questions or question in current_questions):
                col["selected"] = True

            update_multi_select_column(question, col)

        requires_case = self.custom_export.uses_cases()

        case_cols = filter(lambda col: col["index"] == FORM_CASE_ID_PATH, column_conf)
        if not requires_case:
            for col in case_cols:
                if col['index'] == FORM_CASE_ID_PATH:
                    col['tag'], col['show'], col['selected'] = 'deleted', False, False
                    col['allOptions'] = []
        elif not case_cols:
            column_conf.append({
                'index': FORM_CASE_ID_PATH,
                'show': True,
                'is_sensitive': False,
                'selected': True,
                'transform': None,
                'tag': None,
                'display': '',
                'doc_type': None,
                'allOptions': None,
                'options': []
            })

        # This adds [info] location.#text to the standard list of columns to export, even if no forms have been
        # submitted with location data yet.
        if (self.custom_export.app
                and not self.custom_export.app.is_remote_app()
                and self.custom_export.app.auto_gps_capture):
            loc_present = False
            for col in column_conf:
                if col['index'] == 'form.meta.location.#text':
                    loc_present = True
            if not loc_present:
                column_conf.append({
                    'index': 'form.meta.location.#text',
                    'show': True,
                    'is_sensitive': False,
                    'selected': False,
                    'transform': None,
                    'tag': None,
                    'display': '',
                    'doc_type': None,
                    'allOptions': None,
                    'options': []
                })

        column_conf.extend(generate_additional_columns(requires_case))

        def get_remainder_column(question):
            col = ExportColumn(
                index=question,
                display='',
                show=True,
            ).to_config_format(selected=self.creating_new_export)

            update_multi_select_column(question, col)

            return col

        column_conf.extend([
            get_remainder_column(q)
            for q in remaining_questions
        ])

        # show all questions in repeat groups by default
        for conf in table_conf:
            if conf["index"].startswith('#.form.'):
                for col in conf.get("column_configuration", []):
                    col["show"] = True


        table_conf[0]["column_configuration"] = column_conf
        return table_conf

    def get_context(self):
        ctxt = super(FormCustomExportHelper, self).get_context()
        self.update_table_conf_with_questions(ctxt["table_configuration"])
        return ctxt

class CustomColumn(object):

    def __init__(self, slug, index, display, transform, is_sensitive=False, tag=None, show=False, selected=False):
        self.slug = slug
        self.index = index
        self.display = display
        self.transform = transform
        self.is_sensitive = is_sensitive
        self.tag = tag
        self.show = show
        self.selected = selected

    def match(self, col):
         return col['index'] == self.index and col['transform'] == self.transform

    def format_for_javascript(self, col):
        # this is js --> js conversion so the name is pretty bad
        # couch --> javascript UI code
        col['special'] = self.slug

    def default_column(self):
        # this is kinda hacky - mirrors ExportColumn.to_config_format to add custom columns
        # to the existing export UI
        return {
            'index': self.index,
            'selected': self.selected,
            'display': self.display,
            'transform': self.transform,
            "is_sensitive": self.is_sensitive,
            'tag': self.tag,
            'special': self.slug,
            'show': self.show,
            'doc_type': None,
            'allOptions': None,
            'options': []
        }


class CaseCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = CaseExportSchema
    ExportReport = export.CaseExportReport

    export_type = 'case'

    default_properties = ["_id", "closed", "closed_on", "modified_on", "opened_on", "info.owner_name", "id"]
    properties_to_show = ["identifier", "referenced_id", "referenced_type", "id", "doc_type"]
    default_transformed_properties = ["info.closed_by_username", "info.last_modified_by_username",
                                      "info.opened_by_username", "info.owner_name"]
    meta_properties = ["_id", "closed", "closed_by", "closed_on", "domain", "computed_modified_on_",
                       "server_modified_on", "modified_on", "opened_by", "opened_on", "owner_id",
                       "user_id", "type", "version", "external_id"]
    server_properties = ["_rev", "doc_type", "-deletion_id", "initial_processing_complete"]
    row_properties = ["id"]

    @property
    def export_title(self):
        return _('Export Cases and Users')

    def format_config_for_javascript(self, table_configuration):
        custom_columns = [
            CustomColumn(slug='last_modified_by_username', index='user_id',
                         display='info.last_modified_by_username', transform=USERNAME_TRANSFORM),
            CustomColumn(slug='opened_by_username', index='opened_by',
                         display='info.opened_by_username', transform=USERNAME_TRANSFORM),
            CustomColumn(slug='closed_by_username', index='closed_by',
                         display='info.closed_by_username', transform=USERNAME_TRANSFORM),
            CustomColumn(slug='owner_name', index='owner_id', display='info.owner_name',
                         transform=OWNERNAME_TRANSFORM),
        ]
        main_table_columns = table_configuration[0]['column_configuration']
        for custom in custom_columns:
            matches = filter(custom.match, main_table_columns)
            if not matches:
                main_table_columns.append(custom.default_column())
            else:
                for match in matches:
                    custom.format_for_javascript(match)

        return table_configuration

    def update_table_conf(self, table_conf):
        column_conf = table_conf[0].get("column_configuration", [])
        current_properties = set(self.custom_export.case_properties)
        remaining_properties = current_properties.copy()

        def is_special_type(p):
            return any([p in self.meta_properties, p in self.server_properties, p in self.row_properties])

        def update_multi_select_column(col):
            if self.creating_new_export:
                col["options"] = []
                col["allOptions"] = []
            else:
                current_options = col.get("options", [])
                col["allOptions"] = current_options

            return col

        for col in column_conf:
            prop = col["index"]
            display = col.get('display') or prop
            if prop in remaining_properties:
                remaining_properties.discard(prop)
                col["show"] = True
            if not is_special_type(prop) and prop not in current_properties:
                col["tag"] = "deleted"
                col["show"] = False
            if prop in self.default_properties + list(current_properties) or \
                            display in self.default_transformed_properties:
                col["show"] = True
                if self.creating_new_export:
                    col["selected"] = True

            update_multi_select_column(col)

        column_conf.extend([
            update_multi_select_column(ExportColumn(
                index=prop,
                display='',
                show=True,
            ).to_config_format(selected=self.creating_new_export))
            for prop in filter(lambda prop: not prop.startswith("parent/"), remaining_properties)
        ])

        table_conf[0]["column_configuration"] = column_conf

        for table in table_conf:
            for col in table.get("column_configuration", []):
                if col["index"] in self.properties_to_show:
                    col["show"] = True

        # Show most of the Case History rows by default
        dont_show_cols = {"sync_log_id"}
        for table in table_conf:
            if table.get("index", "") == "#.actions.#":
                for col in table.get("column_configuration", []):
                    index = col.get("index", "")
                    if index not in dont_show_cols:
                        col["show"] = True
                    else:
                        dont_show_cols.discard(index)
                break

        return table_conf

    def get_context(self):
        ctxt = super(CaseCustomExportHelper, self).get_context()
        self.update_table_conf(ctxt["table_configuration"])
        return ctxt


def make_custom_export_helper(request, export_type, domain=None, export_id=None):
    export_type = export_type or request.GET.get('request_type', 'form')
    minimal = bool(request.GET.get('minimal', False))
    return {
        'form': FormCustomExportHelper,
        'case': CaseCustomExportHelper,
    }[export_type](request, domain, export_id=export_id, minimal=minimal)
