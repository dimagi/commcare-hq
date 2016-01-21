"""Test S3 Blob DB

Commands to setup Docker with Riak CS for development/testing

First, [install Docker](https://docs.docker.com/mac/#h_installation). Then
initialize a docker machine for Riak CS:

    git clone https://github.com/hectcastro/docker-riak-cs
    cd docker-riak-cs
    docker-machine create --driver virtualbox riakcs
    eval "$(docker-machine env riakcs)"
    # recommended 5-node cluster is slow and resource hungry; use 1 node
    DOCKER_RIAK_CS_CLUSTER_SIZE=1 make start-cluster

Test Riak CS connection:

    DOCKER_RIAKCS_HOST=$(echo $DOCKER_HOST | cut -d/ -f3 | cut -d: -f1)
    DOCKER_RIAKCS_PORT=$(docker port riak-cs01 8080 | cut -d: -f2)
    curl -i http://$DOCKER_RIAKCS_HOST:$DOCKER_RIAKCS_PORT; echo ""
    # expected output:
    # HTTP/1.1 403 Forbidden
    # Server: Riak CS ...

Get admin-key and admin-secret from riak-cs01 container:

    RIAKCS_SSH_PORT=$(docker port riak-cs01 22 | cut -d: -f2)
    ssh -i .insecure_key -p $RIAKCS_SSH_PORT root@$DOCKER_RIAKCS_HOST \
        'egrep "admin_key|admin_secret" /etc/riak-cs/app.config'
    # copy key values into localsettings.py S3_BLOB_DB_SETTINGS (see below)

Finally, add the following to `localsettings.py`:

    def _get_riak_params():
        # these can change depending on host state
        import os, re, subprocess
        def run(command, pattern=None, group=1):
            out = subprocess.check_output(command.split())
            return re.search(pattern, out).group(group) if pattern else out
        try:
            evars = run("docker-machine env riakcs")
            for match in re.finditer(r'export (.*?)="(.*?)"', evars):
                os.environ[match.group(1)] = match.group(2)
            host = re.search(r'DOCKER_HOST="tcp://(.*?):', evars).group(1)
            port = run("docker port riak-cs01 8080", r':(\d+)')
            return {"host": host, "port": port}
        except Exception:
            return None  # docker host is not running
    _riak_params = _get_riak_params()
    if _riak_params:
        S3_BLOB_DB_SETTINGS = {
            "url": "http://{host}:{port}".format(**_riak_params),
            "access_key": "admin key value",
            "secret_key": "admin secret value",
        }
"""
from __future__ import unicode_literals
from os.path import join
from unittest import TestCase, SkipTest
from StringIO import StringIO

from django.conf import settings

import corehq.blobs.s3db as mod
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.util.test_utils import generate_cases


class TestS3BlobDB(TestCase):

    @classmethod
    def setUpClass(cls):
        # use trap_extra_setup when Riak CS is setup on travis (or maybe
        # use something more lightweight like the options mentioned on
        # http://stackoverflow.com/questions/6615988)
        #with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
        s3_settings = getattr(settings, "S3_BLOB_DB_SETTINGS", None)
        if s3_settings is None:
            raise SkipTest("S3_BLOB_DB_SETTINGS not configured")
        cls.db = TemporaryS3BlobDB(s3_settings)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_put_and_get(self):
        name = "test.1"
        info = self.db.put(StringIO(b"content"), name)
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_unicode_names(self):
        name = "test.\u4500"
        bucket = "doc.4500"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_bucket(self):
        name = "test.2"
        bucket = "doc.2"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_with_bucket_and_get_without_bucket(self):
        name = "test.3"
        bucket = "doc.3"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name)

    def test_delete(self):
        name = "test.4"
        bucket = "doc.4"
        info = self.db.put(StringIO(b"content"), name, bucket)

        self.assertTrue(self.db.delete(info.name, bucket), 'delete failed')

        with self.assertRaises(mod.NotFound):
            self.db.get(info.name, bucket)

        # boto3 client reports that the object was deleted even if there was
        # no object to delete
        #self.assertFalse(self.db.delete(info.name, bucket), 'delete should fail')

    def test_delete_bucket(self):
        bucket = join("doctype", "ys7v136b")
        info = self.db.put(StringIO(b"content"), bucket=bucket)
        self.assertTrue(self.db.delete(bucket=bucket))

        self.assertTrue(info.name)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name, bucket=bucket)


@generate_cases([
    ("test.1", "\u4500.1"),
    ("test.1", "/tmp/notallowed"),
    ("test.1", "."),
    ("test.1", ".."),
    ("test.1", "../notallowed"),
    ("test.1", "notallowed/.."),
    ("/test.1",),
    ("../test.1",),
], TestS3BlobDB)
def test_bad_name(self, name, bucket=mod.DEFAULT_BUCKET):
    with self.assertRaises(mod.BadName):
        self.db.get(name, bucket)
