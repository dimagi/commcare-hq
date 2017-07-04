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

from corehq.blobs.tests.util import get_id, TemporaryS3BlobDB
from corehq.blobs.tests.test_fsdb import _BlobDBTests
from corehq.util.test_utils import trap_extra_setup


class TestS3BlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_bucket_path(self):
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        self.assertEqual(self.db.get_path(bucket=bucket), bucket)
