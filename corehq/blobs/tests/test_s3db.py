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

            # reduce timeouts to make tests fail faster
            "config": {"connect_timeout": 1, "read_timeout": 1}
        }

## Alternate/easier/faster testing setup using moto (probably not as robust)

    mkdir moto-s3 && cd moto-s3
    virtualenv env
    git clone https://github.com/dimagi/moto.git
    env/bin/pip install -e ./moto
    env/bin/moto_server -p 5000

Add the following to localsettings.py

    S3_BLOB_DB_SETTINGS = {"url": "http://127.0.0.1:5000"}

"""
from __future__ import unicode_literals
from os.path import join
from unittest import TestCase
from StringIO import StringIO

from django.conf import settings
from testil import tempdir

import corehq.blobs.s3db as mod
from corehq.blobs.exceptions import ArgumentError
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.util.test_utils import generate_cases, trap_extra_setup


class TestS3BlobDB(TestCase):

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_put_and_get(self):
        name = "test.1"
        info = self.db.put(StringIO(b"content"), name)
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_unicode_names(self):
        name = "test.\u4500"
        bucket = "doc.4500"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.identifier, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_bucket(self):
        name = "test.2"
        bucket = "doc.2"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.identifier, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_with_bucket_and_get_without_bucket(self):
        name = "test.3"
        bucket = "doc.3"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier)

    def test_put_with_double_dotted_name(self):
        name = "nations..mp3"
        info = self.db.put(StringIO(b"content"), name)
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_from_get_stream(self):
        name = "form.xml"
        old = self.db.put(StringIO(b"content"), name, "old_bucket")
        with self.db.get(old.identifier, "old_bucket") as fh:
            new = self.db.put(fh, name, "new_bucket")
        with self.db.get(new.identifier, "new_bucket") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_delete(self):
        name = "test.4"
        bucket = "doc.4"
        info = self.db.put(StringIO(b"content"), name, bucket)

        self.assertTrue(self.db.delete(info.identifier, bucket), 'delete failed')

        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier, bucket)

        # boto3 client reports that the object was deleted even if there was
        # no object to delete
        #self.assertFalse(self.db.delete(info.identifier, bucket), 'delete should fail')

    def test_delete_bucket(self):
        bucket = join("doctype", "ys7v136b")
        info = self.db.put(StringIO(b"content"), bucket=bucket)
        self.assertTrue(self.db.delete(bucket=bucket))

        self.assertTrue(info.identifier)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier, bucket=bucket)

    def test_delete_identifier_in_default_bucket(self):
        info = self.db.put(StringIO(b"content"))
        self.assertTrue(self.db.delete(info.identifier), 'delete failed')
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier)

    def test_delete_no_args(self):
        info = self.db.put(StringIO(b"content"))
        with self.assertRaises(ArgumentError):
            self.db.delete()
        # blobs in default bucket should not be deleted
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(bucket=mod.DEFAULT_BUCKET))

    def test_prevent_delete_bucket_by_mistake(self):
        info = self.db.put(StringIO(b"content"))
        id_mistake = None
        with self.assertRaises(ArgumentError):
            self.db.delete(id_mistake, mod.DEFAULT_BUCKET)
        # blobs in default bucket should not be deleted
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(bucket=mod.DEFAULT_BUCKET))

    def test_bucket_path(self):
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), bucket=bucket)
        self.assertEqual(self.db.get_path(bucket=bucket), bucket)

    def test_safe_attachment_path(self):
        name = "test.1"
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.identifier.startswith(name + "."), info.identifier)

    def test_unsafe_attachment_path(self):
        name = "\u4500.1"
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.identifier.startswith("unsafe."), info.identifier)

    def test_unsafe_attachment_name(self):
        name = "test/1"  # name with directory separator
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.identifier.startswith("unsafe."), info.identifier)

    def test_empty_attachment_name(self):
        info = self.db.put(StringIO(b"content"))
        self.assertNotIn(".", info.identifier)


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
