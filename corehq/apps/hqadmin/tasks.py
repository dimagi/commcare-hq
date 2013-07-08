from celery.task import task
import time

@task
def sleep(duration=10):
    time.sleep(duration)

