from celery.schedules import crontab
from celery.task import periodic_task
import requests


@periodic_task(run_every=crontab(minute=3, hour=3))  # Run daily at 03h03
def sync_org_units():
    """
    Synchronize DHIS2 Organization Units with local data
    """
    pass


def push_child_entities():
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment and Underlying Risk Assessment programs.
    """
    # TODO: Set cchq_case_id
    pass


def pull_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare.
    """
    # TODO: Add custom field dhis2_organization_unit_id
    pass


@periodic_task(run_every=crontab(minute=4, hour=4))  # Run daily at 04h04
def sync_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare or associate
    already-registered child cases with DHIS2 child entities.
    """
    pass


def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.
    """
    pass
