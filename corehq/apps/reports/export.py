from datetime import date
import os
import tempfile
import uuid
from corehq.apps.app_manager.models import Application
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.models import FormExportSchema
from corehq.elastic import stream_es_query
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
import couchexport
from couchexport.export import get_headers, get_writer, export_raw, get_formatted_rows
from couchexport.models import DefaultExportSchema, Format, SavedExportSchema
from couchexport.util import SerializableFunction

from soil import DownloadBase

class BulkExport(object):

    @property
    def filename(self):
        return "bulk_export.%(ext)s" % {
            'ext': Format.from_format(self.format).extension,
        }

    @property
    def separator(self):
        return "."

    def create(self, export_tags, export_filter, format=Format.XLS_2007, safe_only=False):
        self.export_filter = export_filter
        self.format = format
        self.safe_only = safe_only
        self.generate_export_objects(export_tags)

    def generate_export_objects(self, export_tags):
        self.export_objects = []

    def generate_bulk_file(self):
        configs = list()
        schemas = list()
        checkpoints = list()

        for export_object in self.export_objects:
            config, schema, checkpoint = export_object.get_export_components(filter=self.export_filter)
            configs.append(config)
            schemas.append(schema)
            checkpoints.append(checkpoint)

        writer = get_writer(self.format)

        # generate the headers for the bulk excel file
        headers = self.generate_table_headers(schemas, checkpoints)

        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as tmp:
            writer.open(headers, tmp)

            # now that the headers are set, lets build the rows
            for i, config in enumerate(configs):
                for doc in config.get_docs():
                    if self.export_objects[i].transform:
                        doc = self.export_objects[i].transform(doc)
                    table = get_formatted_rows(
                        doc, schemas[i], separator=self.separator,
                        include_headers=isinstance(self, CustomBulkExport))
                    if isinstance(self, CustomBulkExport):
                        table = self.export_objects[i].trim(table, doc)
                    table = self.export_objects[i].parse_tables(table)
                    writer.write(table)

            writer.close()
        return path

    def generate_table_headers(self, schemas, checkpoints):
        return []

    def generate_table_rows(self, configs, schemas):
        return []


class CustomBulkExport(BulkExport):
    domain = None

    @property
    def filename(self):
        return "%(domain)s_custom_bulk_export_%(date)s" % {
            'domain': self.domain,
            'date': date.today().isoformat(),
        }

    def generate_export_objects(self, export_tags):
        self.export_objects = []
        for tag in export_tags:
            export_id = tag.get('export_id', None)
            export_type = tag.get('type', 'form')
            sheet_name = tag.get('sheet_name', 'Untitled')

            if export_type == 'form':
                ExportSchemaClass = FormExportSchema
            else:
                ExportSchemaClass = SavedExportSchema
            if export_id:
                export_object = ExportSchemaClass.get(export_id)
                export_object.sheet_name = sheet_name
                if not self.safe_only or export_object.is_safe:
                    export_object.update_schema()
                    self.export_objects.append(export_object)

    def generate_table_headers(self, schemas, checkpoints):
        headers = []
        for export_object in self.export_objects:
            headers.extend(export_object.get_table_headers(True))
        return headers

class ApplicationBulkExport(BulkExport):
    export_id = None

    @property
    def filename(self):
        file_ext = Format.from_format(self.format).extension
        filename = "%s.%s" % (self.export_id, file_ext)
        try:
            app = Application.get(self.export_id)
            if app:
                filename = "%s-%s.%s" %(app.name, app.get_id, file_ext)
        except Exception:
            pass
        return filename

    @property
    def separator(self):
        return "|"

    def generate_export_objects(self, export_tags):
        if self.safe_only:
            return []
        self.export_objects = []
        for schema_index in export_tags:
            self.export_objects.append(
                DefaultExportSchema(index=schema_index,
                                    filter_function=SerializableFunction()))

    def generate_table_headers(self, schemas, checkpoints):
        headers = []
        for i, schema in enumerate(schemas):
            if not checkpoints[i]:
                continue
            header = self.export_objects[i].parse_headers(get_headers(schema, separator=self.separator))
            headers.extend(header)
        return headers

    def generate_table_rows(self, configs, schemas):
        return []


class BulkExportHelper(object):

    def __init__(self, domain=None, safe_only=False):
        self.domain = domain
        self.safe_only = safe_only

    @property
    def zip_export(self):
        return True

    def prepare_export(self, export_tags, export_filter):
        self.generate_bulk_files(export_tags, export_filter)

        download = DownloadBase()
        download.set_task(couchexport.tasks.bulk_export_async.delay(
            self,
            download.download_id,
            domain=self.domain
        ))
        return download.get_start_response()

    def generate_bulk_files(self, export_tags, export_filter):
        self.bulk_files = []

    @property
    def get_id(self):
        return uuid.uuid4().hex


class ApplicationBulkExportHelper(BulkExportHelper):

    def generate_bulk_files(self, export_tags, export_filter):
        self.bulk_files = []

        # Sometimes this is None, but it should not crash.
        export_tags = export_tags or {}

        if export_tags:
            for appid, indices in export_tags.items():
                app_bulk_export = ApplicationBulkExport()
                app_bulk_export.create(indices, export_filter)
                app_bulk_export.export_id = appid
                self.bulk_files.append(app_bulk_export)

class CustomBulkExportHelper(BulkExportHelper):

    @property
    def zip_export(self):
        return False

    def generate_bulk_files(self, export_tags, export_filter):
        bulk_export = CustomBulkExport()
        bulk_export.create(export_tags, export_filter, safe_only=self.safe_only)
        bulk_export.domain = self.domain
        self.bulk_files = [bulk_export]

def save_metadata_export_to_tempfile(domain, format, datespan=None, user_ids=None):
    """
    Saves the domain's form metadata to a file. Returns the filename.
    """
    headers = ("domain", "instanceID", "received_on", "type",
               "timeStart", "timeEnd", "deviceID", "username",
               "userID", "xmlns", "version")

    def _form_data_to_row(formdata):
        def _key_to_val(formdata, key):
            if key == "type":
                return xmlns_to_name(domain, formdata.get("xmlns"), app_id=None)
            if key == "version":
                return formdata["form"].get("@version")
            if key in ["domain", "received_on", "xmlns"]:
                return formdata.get(key)
            return formdata["form"].get("meta", {}).get(key)
        return [_key_to_val(formdata, key) for key in headers]

    fd, path = tempfile.mkstemp()

    q = {
        "query": {"match_all": {}},
        "sort": [{"received_on" : {"order": "desc"}}],
        "filter": {"and": []},
    }

    if datespan:
        q["query"] = {
            "range": {
                "form.meta.timeEnd": {
                    "from": datespan.startdate_param,
                    "to": datespan.enddate_param,
                    "include_upper": False,
                }
            }
        }

    if user_ids is not None:
        q["filter"]["and"].append({"terms": {"form.meta.userID": user_ids}})

    results = stream_es_query(params={"domain.exact": domain}, q=q, es_url=XFORM_INDEX + '/xform/_search', size=999999)
    data = (_form_data_to_row(res["_source"]) for res in results)

    with os.fdopen(fd, 'w') as temp:
        export_raw((("forms", headers),), (("forms", data),), temp, format=format)

    return path
