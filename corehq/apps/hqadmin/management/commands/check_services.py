from collections import namedtuple
from StringIO import StringIO
from django.core.management import BaseCommand
from corehq.blobs import get_blob_db


ServiceStatus = namedtuple("ServiceStatus", "success msg")


def test_pillowtop():
    return ServiceStatus(False, "Not implemented")


def test_kafka():
    return ServiceStatus(False, "Not implemented")


def test_redis():
    return ServiceStatus(False, "Not implemented")


def test_postgres():
    return ServiceStatus(False, "Not implemented")


def test_couch():
    return ServiceStatus(False, "Not implemented")


def test_celery():
    return ServiceStatus(False, "Not implemented")


def test_touchforms():
    return ServiceStatus(False, "Not implemented")


def test_elasticsearch():
    return ServiceStatus(False, "Not implemented")


def test_shared_dir():
    return ServiceStatus(False, "Not implemented")


def test_blobdb():
    """Save something to the blobdb and try reading it back."""
    db = get_blob_db()
    contents = "It takes Pluto 248 Earth years to complete one orbit!"
    info = db.put(StringIO(contents))
    with db.get(info.identifier) as fh:
        res = fh.read()
    db.delete(info.identifier)
    if res == contents:
        return ServiceStatus(True, "Successfully saved a file to the blobdb")
    return ServiceStatus(False, "Failed to save a file to the blobdb")


service_tests = (
    test_pillowtop,
    test_kafka,
    test_redis,
    test_postgres,
    test_couch,
    test_celery,
    test_touchforms,
    test_elasticsearch,
    test_shared_dir,
    test_blobdb,
)


class Command(BaseCommand):
    help = 'Check the status of various services'

    def handle(self, *args, **options):
        for service_test in service_tests:
            test_name = service_test.__name__
            try:
                status = service_test()
            except Exception as e:
                print "Service test '{}' errored with exception '{}'".format(
                    test_name,
                    repr(e)
                )
            else:
                print "SUCCESS" if status.success else "FAILURE",
                print "{}: {}".format(test_name, status.msg)
