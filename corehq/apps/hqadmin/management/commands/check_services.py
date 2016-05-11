from collections import namedtuple
from StringIO import StringIO
from django.core.management import BaseCommand
from corehq.blobs import get_blob_db


ServiceStatus = namedtuple("ServiceStatus", "success msg")


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
    return ServiceStatus(False, "Did not successfully save a file to the blobdb")


service_tests = (test_blobdb,)


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
