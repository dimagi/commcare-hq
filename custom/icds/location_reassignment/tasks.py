from celery.task import task

from custom.icds.location_reassignment.processor import Processor


@task
def process_location_reassignment(domain, transitions, site_codes):
    Processor(domain, transitions, site_codes).process()
