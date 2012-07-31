from StringIO import StringIO
import uuid
from django.core.urlresolvers import reverse
from django.http import HttpResponse
import json
import zipfile
from corehq.apps.app_manager.models import Application
import couchexport
from couchexport.export import get_headers, get_writer, format_tables, create_intermediate_tables
from couchexport.models import FakeSavedExportSchema, Format

# couchexport is a mess. Sorry. Sorry. This is gross.

class BaseBulkExport(object):
    export_id = None
    first_checkpoint_id = None

    def __init__(self,
                 schema_indices,
                 export_filter,
                 export_object=FakeSavedExportSchema,
                 format=Format.XLS_2007):
        self.export_objects = list()
        self.export_filter = export_filter
        self.format=format
        for schema_index in schema_indices:
            self.export_objects.append(export_object(index=schema_index))

    @property
    def filename(self):
        return self.export_id if self.export_id else "bulk_export.%s" % Format.from_format(self.format).extension

    def generate_bulk_file(self, separator='|'):
        configs = list()
        schemas = list()
        checkpoints = list()
        file = StringIO()

        print "checkpoint 1"
        print self.export_objects
        for export_object in self.export_objects:
            config, schema, checkpoint = export_object.get_export_components(filter=self.export_filter)
            configs.append(config)
            schemas.append(schema)
            checkpoints.append(checkpoint)
            if checkpoint and not self.first_checkpoint_id:
                # ew
                self.first_checkpoint_id = checkpoint.get_id

        print "point 2"
        # generate the headers for the bulk excel file
        headers = []
        for i, schema in enumerate(schemas):
            if not checkpoints[i]:
                continue
            header = self.export_objects[i].parse_headers(get_headers(schema, separator=separator))

            headers.extend(header)
        print "headers", headers
        writer = get_writer(self.format)
        writer.open(headers, file)

        print "point 3"
        # now that the headers are set, lets build the rows
        for i, config in enumerate(configs):
            for doc in config.get_docs():
                if self.export_objects[i].transform:
                    doc = self.export_objects[i].transform(doc)
                table = format_tables(create_intermediate_tables(doc, schemas[i]),
                                    include_headers=False, separator=separator)
                table = self.export_objects[i].parse_tables(table)
                writer.write(table)

        writer.close()

        return file



class ApplicationBulkExport(BaseBulkExport):

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


class BulkExportHelper(object):
    bulk_files = list()
    domain=None

    def prepare_export(self):
        print "preparing export", self.bulk_files
        download_id = uuid.uuid4().hex
        couchexport.tasks.bulk_export_async.delay(
            self,
            download_id,
            self.bulk_files,
            domain=self.domain
        )
        return HttpResponse(json.dumps(dict(
            download_id=download_id,
            download_url=reverse('ajax_job_poll', kwargs={'download_id': download_id}))
        ))

    @property
    def get_id(self):
        try:
            first_checkpoint_id = self.bulk_files[0].first_checkpoint_id
            return first_checkpoint_id if first_checkpoint_id else ""
        except Exception:
            return ""



class BulkExportPerApplicationHelper(BulkExportHelper):

    def __init__(self, export_tags, export_filter, domain=None):
        self.domain = domain
        for appid, indices in export_tags.items():
            app_bulk_export = ApplicationBulkExport(
                indices,
                export_filter
            )
            app_bulk_export.export_id = appid
            print app_bulk_export
            self.bulk_files.append(app_bulk_export)

        print self.bulk_files
