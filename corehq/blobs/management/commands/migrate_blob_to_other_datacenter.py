from collections import namedtuple
from cStringIO import StringIO
from getpass import getpass
import json
from optparse import make_option
from os.path import join
import zipfile

from django.conf import settings
from django.core.management.base import BaseCommand

from couchforms.models import XFormInstance
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.hqmedia.models import CommCareMultimedia

from corehq.blobs import get_blob_db
from corehq.blobs.mixin import _get_couchdb_name, safe_id
from corehq.blobs.exceptions import NotFound

BlobInfo = namedtuple('BlobInfo', ['type', 'id', 'external_blob_ids'])
MockSettings = namedtuple('MockSettings', ['S3_BLOB_DB_SETTINGS'])


class Command(BaseCommand):
    help = "Command to migrate a domain's attachments in the blobdb to a new blobdb"
    args = '<domain>'
    option_list = BaseCommand.option_list + (
        make_option('--from-riak-url',
            action='store',
            dest='from_riak_url',
            default='',
            help='The URL of the Riak instance you are migrating from'
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
        make_option('--output-jsonl-file',
            action='store',
            dest='output_jsonl',
            default='blobs.jsonl',
        ),
        make_option('--no-zip-file',
            action='store_false',
            dest='zip_file',
            default=True,
        ),
    )

    def handle(self, *args, **options):
        domain = args[0]

        from_riak_settings = {}
        if options['from_riak_url']:
            access_key = getpass("Please enter the from riak access key: ")
            secret_key = getpass("Please enter the from riak secret key: ")
            from_riak_settings = {
                'url': options['from_riak_url'],
                'access_key': access_key,
                'secret_key': secret_key,
                'config': {'connect_timeout': 3, 'read_timeout': 5},
            }

        blobs_to_copy = []
        blobs_to_copy.extend(get_saved_exports_blobs(domain))
        blobs_to_copy.extend(get_applications_blobs(domain))
        blobs_to_copy.extend(get_multimedia_blobs(domain))
        blobs_to_copy.extend(get_xforms_blobs(domain))

        with open(options['output_jsonl'], 'w') as f:
            for doc in blobs_to_copy:
                f.write(json.dumps(doc._asdict()))
                f.write('\n')

        if from_riak_settings:
            db = get_blob_db(MockSettings(from_riak_settings))
        else:
            db = get_blob_db()

        to_riak_settings = {}
        to_db = None
        if options['to_riak_url']:
            access_key = getpass("Please enter the to riak access key: ")
            secret_key = getpass("Please enter the to riak secret key: ")
            from_riak_settings = {
                'url': options['to_riak_url'],
                'access_key': access_key,
                'secret_key': secret_key,
                'config': {'connect_timeout': 3, 'read_timeout': 5},
            }
            to_db = get_blob_db(to_riak_settings)


        blob_zipfile = None
        if options['zip_file']:
            zfile = open(options['output_zip'], 'wb')
            blob_zipfile = zipfile.ZipFile(zfile, 'w')

        for info in blobs_to_copy:
            bucket = join(_get_couchdb_name(eval(info.type)), safe_id(info.id))
            for blob_id in info.external_blob_ids:
                try:
                    blob = db.get(blob_id, bucket).read()
                except NotFound as e:
                    print('Blob Not Found: ' + str(e))
                else:
                    if blob_zipfile:
                        zip_info = zipfile.ZipInfo(join(bucket, blob_id))
                        blob_zipfile.writestr(zip_info, blob)
                    if to_db:
                        print('writing blob ' + zip_info.filename)
                        if isinstance(blob, unicode):
                            content = StringIO(blob.encode("utf-8"))
                        elif isinstance(blob, bytes):
                            content = StringIO(blob)
                        else:
                            content = blob
                        to_db.put(content, blob_id, bucket)

        if blob_zipfile:
            blob_zipfile.close()
            zfile.close()


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
    xforms = XFormInstance.get_db().view(
        'couchforms/all_submissions_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()
    return _format_return_value('XFormInstance', xforms)


def _format_return_value(type, docs):
    return [
        BlobInfo(type, doc['id'],
            [blob['id'] for blob in doc['doc']['external_blobs'].values()]
        )
        for doc in docs
    ]
