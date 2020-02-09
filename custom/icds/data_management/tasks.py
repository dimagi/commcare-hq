from celery.task import task

from custom.icds.data_management.models import DataManagementRequest


@task(queue='background_queue')
def execute_data_management(slug, domain, db_alias, initiated_by, from_date, till_date):
    DataManagementRequest(
        slug, domain, db_alias, initiated_by, from_date, till_date
    ).execute()
