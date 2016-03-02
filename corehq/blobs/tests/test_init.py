import re
from os.path import join

from django.test import override_settings
from mock import patch
from testil import assert_raises, tempdir

import corehq.blobs as mod
from corehq.util.test_utils import generate_cases
from settingshelper import SharedDriveConfiguration


@generate_cases([
    dict(root=None, msg=r"invalid shared drive path: None$"),
    dict(root="", msg=r"invalid shared drive path: ''$"),
    dict(root="file", msg=r"shared drive path is not a directory: '.*/file'$"),
    dict(blob_dir=None, msg="blob_dir is empty or not configured"),
    dict(blob_dir="", msg="blob_dir is empty or not configured"),
])
def test_get_blobdb(self, msg, root=True, blob_dir=None):
    with tempdir() as tmp:
        if root == "file":
            tmp = join(tmp, "file")
            with open(tmp, "w") as fh:
                fh.write("x")
        conf = SharedDriveConfiguration(
            shared_drive_path=tmp if root else root,
            restore_dir=None,
            transfer_dir=None,
            temp_dir=None,
            blob_dir=blob_dir,
        )
        with patch("corehq.blobs._db", new=[]):
            with override_settings(SHARED_DRIVE_CONF=conf, S3_BLOB_DB_SETTINGS=None):
                with assert_raises(mod.Error, msg=re.compile(msg)):
                    mod.get_blob_db()
