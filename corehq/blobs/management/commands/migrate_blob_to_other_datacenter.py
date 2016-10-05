from collections import namedtuple
from cStringIO import StringIO
from getpass import getpass
import json
from optparse import make_option
from os.path import join
import zipfile

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.es.forms import FormES
from corehq.apps.hqmedia.models import CommCareMultimedia

from corehq.blobs import get_blob_db
from corehq.blobs.mixin import _get_couchdb_name, safe_id
from corehq.blobs.exceptions import NotFound

BlobInfo = namedtuple('BlobInfo', ['type', 'id', 'external_blobs'])
MockSettings = namedtuple('MockSettings', ['S3_BLOB_DB_SETTINGS'])

JSONL_NAME_IN_ZIPFILE = "blobs.jsonl"


class Command(BaseCommand):
    help = "Command to migrate a domain's attachments in the blobdb to a new blobdb"
    args = '<domain>'
    option_list = BaseCommand.option_list + (
        make_option('--domain',
            action='store',
            dest='domain',
            default='',
            help='Domain you are copying from. Required if using --from-riak-url'
        ),
        make_option('--from-riak-url',
            action='store',
            dest='from_riak_url',
            default='',
            help='The URL of the Riak instance you are migrating from'
        ),
        make_option('--from-zip-file',
            action='store',
            dest='from_zip_filename',
            default='',
            help='The filename of the zip you want to read from. Implies you cannot write to zipfile'
        ),
        make_option('--to-riak-url',
            action='store',
            dest='to_riak_url',
            default='',
            help='The URL of the Riak instance you are migrating to'
        ),
        make_option('--output-zip-file',
            action='store',
            dest='output_zip',
            default='blobs.zip',
        ),
        make_option('--no-zip-file',
            action='store_false',
            dest='zip_file',
            default=True,
        ),
    )
    from_db = None
    from_zip = None
    to_db = None
    to_zip = None

    def handle(self, *args, **options):
        if options['from_riak_url'] and not options['domain']:
            raise ValueError("Must provide domain if copying from riak")

        self._set_from_data_source(options)
        blobs = self._get_blobs_to_copy(options)

        self._set_to_data_source(options, blobs)
        self.output_blobs(blobs)
        self.cleanup()

    def cleanup(self):
        if self.to_zip:
            self.to_zip.close()

    def output_blobs(self, blobs):
        for info in blobs:
            bucket = join(_get_couchdb_name(eval(info.type)), safe_id(info.id))
            for external_blob in info.external_blobs.values():
                blob_id = external_blob['id']
                try:
                    blob = self._get_blob(bucket, blob_id)
                except NotFound as e:
                    print('Blob Not Found: ' + str(e))
                else:
                    if self.to_zip:
                        zip_info = zipfile.ZipInfo(join(bucket, blob_id))
                        self.to_zip.writestr(zip_info, blob)
                    if self.to_db:
                        print('writing blob ' + zip_info.filename)
                        if isinstance(blob, unicode):
                            content = StringIO(blob.encode("utf-8"))
                        elif isinstance(blob, bytes):
                            content = StringIO(blob)
                        else:
                            content = blob
                        self.to_db.put(content, blob_id, bucket)

    def _set_from_data_source(self, options):
        riak_settings = {}
        if options['from_riak_url']:
            riak_settings = get_riak_settings(options['from_riak_url'])
        elif options['from_zip_filename']:
            self.from_zip = zipfile.ZipFile(options['from_zip_filename'])

        if not self.from_zip:
            if riak_settings:
                self.from_db = get_blob_db(MockSettings(riak_settings))
            else:
                self.from_db = get_blob_db()

    def _set_to_data_source(self, options, blobs_to_copy):
        riak_settings = {}
        self.to_db = None
        if options['to_riak_url']:
            riak_settings = get_riak_settings(options['to_riak_url'])
            self.to_db = get_blob_db(riak_settings)

        self.to_zip = None
        if options['zip_file'] or not self.from_zip:
            zfile = open(options['output_zip'], 'wb')
            self.to_zip = zipfile.ZipFile(zfile, 'w')

            blobs_to_copy_str = ""
            for doc in blobs_to_copy:
                blobs_to_copy_str += json.dumps(doc._asdict()) + "\n"

            zip_info = zipfile.ZipInfo(JSONL_NAME_IN_ZIPFILE)
            self.to_zip.writestr(zip_info, blobs_to_copy_str)

    def _get_blobs_to_copy(self, options=None):
        domain = options['domain']
        blobs_to_copy = []
        if self.from_db:
            blobs_to_copy.extend(get_saved_exports_blobs(domain))
            blobs_to_copy.extend(get_applications_blobs(domain))
            blobs_to_copy.extend(get_multimedia_blobs(domain))
            blobs_to_copy.extend(get_xforms_blobs(domain))
        else:
            blobs_to_copy_file = self.from_zip.open(JSONL_NAME_IN_ZIPFILE)
            for line in blobs_to_copy_file:
                blobs_to_copy.append(BlobInfo(**json.loads(line)))

        return blobs_to_copy

    def _get_blob(self, bucket, blob_id):
        if self.from_db:
            return self.from_db.get(blob_id, bucket).read()
        elif self.from_zip:
            return self.from_zip.open(join(bucket, blob_id))
        else:
            raise Exception("Don't know what happened here")


def get_riak_settings(riak_url):
    print("the following options are for the from riak server ({0})".format(riak_url))
    access_key = getpass("Please enter the riak access key: ")
    secret_key = getpass("Please enter the riak secret key: ")
    riak_settings = {
        'url': riak_url,
        'access_key': access_key,
        'secret_key': secret_key,
        'config': {'connect_timeout': 3, 'read_timeout': 5},
    }
    return riak_settings


def get_saved_exports_blobs(domain):
    # I think that this is only for caching exports, so not implementing
    return []


def get_applications_blobs(domain):
    apps = []
    apps.extend(Application.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'Application', None],
        endkey=[domain, 'Application', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(Application.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'Application-Deleted', None],
        endkey=[domain, 'Application-Deleted', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(RemoteApp.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'RemoteApplication', None],
        endkey=[domain, 'RemoteApplication', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(RemoteApp.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'RemoteApplication-Deleted', None],
        endkey=[domain, 'RemoteApplication-Deleted', None, {}],
        include_docs=True,
        reduce=False,
    ).all())

    return _format_return_value('Application', apps)


def get_multimedia_blobs(domain):
    media = CommCareMultimedia.get_db().view(
        'hqmedia/by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()
    return _format_return_value('CommCareMultimedia', media)


def get_xforms_blobs(domain):
    xforms = (
        FormES()
        .remove_default_filters()
        .domain(domain)
        .source('external_blobs')
        .exists('external_blobs')
        .run().raw_hits
    )
    return [
        BlobInfo('XFormInstance', xform['_id'], xform['_source']['external_blobs'])
        for xform in xforms
    ]


def _format_return_value(type, docs):
    return [
        BlobInfo(type, doc['id'], doc['doc']['external_blobs'])
        for doc in docs
    ]
