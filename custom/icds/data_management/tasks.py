from celery.task import task

from custom.icds.data_management.models import DataManagementRequest


@task(queue='background_queue')
def execute_data_management(slug, domain, db_alias, initiated_by, start_date, end_date):
    processed, skipped = DataManagementRequest(
        slug=slug, domain=domain, db_alias=db_alias, initiated_by=initiated_by,
        start_date=start_date, end_date=end_date
    ).execute()
