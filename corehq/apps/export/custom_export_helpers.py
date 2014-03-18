import json
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege
from corehq import toggles, privileges
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.reports.standard import export
from corehq.apps.reports.models import FormExportSchema, HQGroupExportConfiguration, CaseExportSchema
from corehq.apps.reports.standard.export import DeidExportReport
from couchexport.models import ExportTable, ExportSchema, ExportColumn
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.commtrack.models import StockExportColumn
from corehq.apps.domain.models import Domain


USERNAME_TRANSFORM = 'corehq.apps.export.transforms.user_id_to_username'
OWNERNAME_TRANSFORM = 'corehq.apps.export.transforms.owner_id_to_display'
CASENAME_TRANSFORM = 'corehq.apps.export.transforms.case_id_to_case_name'


class AbstractProperty(object):
    def __get__(self, instance, owner):
        raise NotImplementedError()


class CustomExportHelper(object):

    ExportSchemaClass = AbstractProperty()
    ExportReport = AbstractProperty()
    export_title = AbstractProperty()

    allow_deid = False
    allow_repeats = True

    subclasses_map = {}  # filled in below

    export_type = 'form'

    @property
    def default_order(self):
        return {}

    @classmethod
    def make(cls, request, export_type, domain=None, export_id=None):
        export_type = export_type or request.GET.get('request_type', 'form')
        return cls.subclasses_map[export_type](request, domain, export_id=export_id)

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

    class DEID(object):
        options = (
            ('', ''),
            (_('Sensitive ID'), 'couchexport.deid.deid_ID'),
            (_('Sensitive Date'), 'couchexport.deid.deid_date'),
        )
        json_options = [{'label': label, 'value': value}
                        for label, value in options]

    def __init__(self, request, domain, export_id=None):
        self.request = request
        self.domain = domain
        self.presave = False
        self.transform_dates = False
        self.creating_new_export = not bool(export_id)

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
        return json.loads(self.request.raw_post_data)

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

        if self.presave:
            HQGroupExportConfiguration.add_custom_export(self.domain, self.custom_export.get_id)
        else:
            HQGroupExportConfiguration.remove_custom_export(self.domain, self.custom_export.get_id)

    def get_context(self):
        table_configuration = self.format_config_for_javascript(self.custom_export.table_configuration)
        return {
            'custom_export': self.custom_export,
            'default_order': self.default_order,
            'deid_options': self.DEID.json_options,
            'presave': self.presave,
            'export_stock': self.export_stock,
            'DeidExportReport_name': DeidExportReport.name,
            'table_configuration': table_configuration,
            'domain': self.domain,
            'commtrack_domain': Domain.get_by_name(self.domain).commtrack_enabled,
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

    default_questions = ["form.case.@case_id", "form.meta.timeEnd", "_id", "id", "form.meta.username"]
    questions_to_show = default_questions + ["form.meta.timeStart", "received_on"]

    @property
    def export_title(self):
        return _('Export Submissions to Excel')

    def __init__(self, request, domain, export_id=None):
        super(FormCustomExportHelper, self).__init__(request, domain, export_id)
        if not self.custom_export.app_id:
            self.custom_export.app_id = request.GET.get('app_id')

    @property
    def allow_deid(self):
        try:
            ensure_request_has_privilege(self.request, privileges.DEIDENTIFIED_DATA)
            return True
        except PermissionDenied:
            return False

    def update_custom_params(self):
        p = self.post_data['custom_export']
        e = self.custom_export
        e.include_errors = p['include_errors']
        e.app_id = p['app_id']

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

        def generate_additional_columns():
            ret = []
            case_name_col = CustomColumn(slug='case_name', index='form.case.@case_id', display='info.case_name',
                                     transform=CASENAME_TRANSFORM, show=True, selected=True)
            matches = filter(case_name_col.match, column_conf)
            if matches:
                for match in matches:
                    case_name_col.format_for_javascript(match)
            elif filter(lambda col: col["index"] == case_name_col.index, column_conf):
                ret.append(case_name_col.default_column())
            return ret

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

        column_conf.extend(generate_additional_columns())
        column_conf.extend([
            ExportColumn(
                index=q,
                display='',
                show=True,
            ).to_config_format(selected=self.creating_new_export)
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
        return _('Export Cases, Referrals, and Users')

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

        column_conf.extend([
            ExportColumn(
                index=prop,
                display='',
                show=True,
            ).to_config_format(selected=self.creating_new_export)
            for prop in filter(lambda prop: not prop.startswith("parent/"), remaining_properties)
        ])

        table_conf[0]["column_configuration"] = column_conf

        for table in table_conf:
            for col in table.get("column_configuration", []):
                if col["index"] in self.properties_to_show:
                    col["show"] = True

        return table_conf

    def get_context(self):
        ctxt = super(CaseCustomExportHelper, self).get_context()
        self.update_table_conf(ctxt["table_configuration"])
        return ctxt


CustomExportHelper.subclasses_map.update({
    'form': FormCustomExportHelper,
    'case': CaseCustomExportHelper,
})
