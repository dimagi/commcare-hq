from __future__ import absolute_import
from __future__ import unicode_literals

from io import open
from celery.task import task

from corehq.apps.app_manager.dbaccessors import get_build_by_version
from corehq.apps.hqmedia.tasks import create_ccz_files
from corehq.apps.app_manager.dbaccessors import wrap_app
from custom.icds.models import CCZHosting
from custom.icds_reports.models.helper import IcdsFile


@task
def setup_ccz_file_for_hosting(ccz_hosting_id):
    try:
        ccz_hosting = CCZHosting.objects.get(pk=ccz_hosting_id)
    except CCZHosting.DoesNotExist:
        return
    version = ccz_hosting.version
    ccz_blob_id = ccz_hosting.blob_id
    build = wrap_app(get_build_by_version(ccz_hosting.link.domain, ccz_hosting.app_id, version))
    # set up the file if not already present
    if not IcdsFile.objects.filter(blob_id=ccz_blob_id, data_type="ccz").exists():
        icds_file = IcdsFile(blob_id=ccz_blob_id, data_type="ccz")
        ccz_file = create_ccz_files(build, None)
        ccz_file_name = "commcare_v%s.ccz" % version
        try:
            with open(ccz_file, 'rb') as ccz:
                icds_file.store_file_in_blobdb(ccz, name=ccz_file_name)
                icds_file.save()
        except Exception as e:
            # delete the file from blob db if it was added but save failed
            icds_file.remove_file_from_blobdb()
            raise e
