from celery.task.base import task
import logging
from custom.logistics.commtrack import resync_password


@task
def resync_webusers_passwords_task(config, endpoint):
    logging.info("Logistics: Webusers passwords resyncing started")
    _, webusers = endpoint.get_webusers(limit=2000)

    for webuser in webusers:
        resync_password(config, webuser)

    logging.info("Logistics: Webusers passwords resyncing finished")