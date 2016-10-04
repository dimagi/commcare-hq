from collections import namedtuple
import json
from optparse import make_option
from os.path import join
import zipfile

from django.core.management.base import BaseCommand

from couchforms.models import XFormInstance
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.hqmedia.models import CommCareMultimedia

from corehq.blobs import get_blob_db
from corehq.blobs.mixin import _get_couchdb_name, safe_id
from corehq.blobs.exceptions import NotFound

BlobInfo = namedtuple('BlobInfo', ['type', 'id', 'external_blob_ids'])


class Command(BaseCommand):
    help = "Command to migrate a domain's attachments in the blobdb to a new blobdb"
    args = '<domain>'
    option_list = BaseCommand.option_list + ()

    def handle(self, *args, **options):
        domain = args[0]
        blobs_to_copy = []
        blobs_to_copy.extend(get_saved_exports_blobs(domain))
        blobs_to_copy.extend(get_applications_blobs(domain))
        blobs_to_copy.extend(get_multimedia_blobs(domain))
        blobs_to_copy.extend(get_xforms_blobs(domain))

        with open('blobs.jsonl', 'w') as f:
            for doc in blobs_to_copy:
                f.write(json.dumps(doc._asdict()))
                f.write('\n')

        db = get_blob_db()

        with open('blobs.zip', 'wb') as zfile:
            with zipfile.ZipFile(zfile, 'w') as blob_zipfile:
                for info in blobs_to_copy:
                    bucket = join(_get_couchdb_name(eval(info.type)), safe_id(info.id))
                    for blob_id in info.external_blob_ids:
                        try:
                            zip_info = zipfile.ZipInfo(join(bucket, blob_id))
                            blob_zipfile.writestr(zip_info, db.get(blob_id, bucket).read())
                        except NotFound as e:
                            print('Blob Not Found: ' + str(e))


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
