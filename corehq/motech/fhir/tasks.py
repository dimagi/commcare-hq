from celery.schedules import crontab
from celery.task import periodic_task

from corehq import toggles
from corehq.motech.requests import Requests

from .const import IMPORT_FREQUENCY_DAILY
from .models import FHIRImporter, FHIRImporterResourceType


@periodic_task(run_every=crontab(hour=5, minute=5), queue='background_queue')
def run_daily_importers():
    for importer in (
        FHIRImporter.objects.filter(
            frequency=IMPORT_FREQUENCY_DAILY
        ).select_related('connection_settings').all()
    ):
        run_importer(importer)


def run_importer(importer):
    """
    Poll remote API and import resources as CommCare cases.

    ServiceRequest resources are treated specially for workflows that
    handle referrals across systems like CommCare.
    """
    if not toggles.FHIR_INTEGRATION.enabled(importer.domain):
        return
    requests = importer.connection_settings.get_requests()
    # TODO: Check service is online, else retry with exponential backoff
    for resource_type in (
            importer.resource_types
            .filter(import_related_only=False)
            .prefetch_related('jsonpaths_to_related_resource_types')
            .all()
    ):
        import_resource_type(requests, resource_type)


def import_resource_type(
    requests: Requests,
    resource_type: FHIRImporterResourceType,
):
    pass
