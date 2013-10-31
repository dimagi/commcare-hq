import json
from corehq.apps.reports.standard import export
from corehq.apps.reports.models import FormExportSchema, HQGroupExportConfiguration, HQExportSchema
from corehq.apps.reports.standard.export import DeidExportReport
from couchexport.models import ExportTable, ExportSchema, ExportColumn
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized


USERNAME_TRANSFORM = 'corehq.apps.users.util.user_id_to_username_export_transform'

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
        pass

    def format_config_for_javascript(self, table_configuration):
        return table_configuration

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

        if export_id:
            self.custom_export = self.ExportSchemaClass.get(export_id)
            # also update the schema to include potential new stuff
            self.custom_export.update_schema()

            # enable configuring saved exports from this page
            saved_group = HQGroupExportConfiguration.get_for_domain(self.domain)
            self.presave = export_id in saved_group.custom_export_ids

            assert(self.custom_export.doc_type == 'SavedExportSchema')
            assert(self.custom_export.type == self.export_type)
            assert(self.custom_export.index[0] == domain)
        else:
            self.custom_export = self.ExportSchemaClass(type=self.export_type)

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
            'DeidExportReport_name': DeidExportReport.name,
            'table_configuration': table_configuration,
            'domain': self.domain,
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

    allow_deid = True
    allow_repeats = True

    @property
    def export_title(self):
        return _('Export Submissions to Excel')

    def __init__(self, request, domain, export_id=None):
        super(FormCustomExportHelper, self).__init__(request, domain, export_id)
        if not self.custom_export.app_id:
            self.custom_export.app_id = request.GET.get('app_id')

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
        column_conf = table_conf[0].get("column_configuration", {})
        current_questions = set(self.custom_export.question_order)
        remaining_questions = current_questions.copy()

        def is_special_type(q):
            return any([q.startswith('form.#'), q.startswith('form.@'), q.startswith('form.case.'), q.startswith('form.meta.')])

        for col in column_conf:
            question = col["index"]
            remaining_questions.discard(question)
            if question.startswith("form.") and not is_special_type(question) and question not in current_questions:
                col["tag"] = "deleted"

        column_conf.extend([
            ExportColumn(
                index=q,
                display='',
                tag='no data',
            ).to_config_format(selected=False)
            for q in remaining_questions
        ])

        table_conf[0]["column_configuration"] = column_conf
        return table_conf

    def get_context(self):
        ctxt = super(FormCustomExportHelper, self).get_context()
        self.update_table_conf_with_questions(ctxt["table_configuration"])
        return ctxt

class CustomColumn(object):

    def __init__(self, slug, index, display, transform):
        self.slug = slug
        self.index = index
        self.display = display
        self.transform = transform

    def match(self, col):
         return col['index'] == self.index and col['transform'] == self.transform

    def format_for_javascript(self, col):
        # this is js --> js conversion so the name is pretty bad
        # couch --> javascript UI code
        col['special'] = self.slug

    def default_column(self):
        return {
            'index': self.index,
            'selected': False,
            'display': self.display,
            'transform': self.transform,
            'special': self.slug,
        }


class CaseCustomExportHelper(CustomExportHelper):

    ExportSchemaClass = HQExportSchema
    ExportReport = export.CaseExportReport

    export_type = 'case'

    @property
    def export_title(self):
        return _('Export Cases, Referrals, and Users')

    def format_config_for_javascript(self, table_configuration):
        custom_columns = [
            CustomColumn(slug='username', index='user_id', display='meta.username', transform=USERNAME_TRANSFORM),
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


CustomExportHelper.subclasses_map.update({
    'form': FormCustomExportHelper,
    'case': CaseCustomExportHelper,
})
