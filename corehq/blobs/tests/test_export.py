import os
import tarfile
import uuid
from io import BytesIO
from tempfile import NamedTemporaryFile

from django.test import TestCase

from corehq.apps.hqmedia.models import CommCareAudio, CommCareVideo, CommCareImage
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.export import EXPORTERS
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta


class TestBlobExport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.db = TemporaryFilesystemBlobDB()
        assert get_blob_db() is cls.db, (get_blob_db(), cls.db)
        data = b'binary data not valid utf-8 \xe4\x94'
        cls.blob_metas = []
        cls.not_found = set()

        cls.domain_name = str(uuid.uuid4)

        for type_code in [CODES.form_xml, CODES.multimedia, CODES.data_export]:
            for domain in (cls.domain_name, str(uuid.uuid4())):
                meta = cls.db.put(BytesIO(data), meta=new_meta(domain=domain, type_code=type_code))
                lost = new_meta(domain=domain, type_code=type_code, content_length=42)
                cls.blob_metas.append(meta)
                cls.blob_metas.append(lost)
                lost.save()
                cls.not_found.add(lost.key)

    @classmethod
    def tearDownClass(cls):
        for blob in cls.blob_metas:
            blob.delete()
        cls.db.close()
        super().tearDownClass()

    def test_migrate_all(self):
        expected = {
            m.key for m in self.blob_metas
            if m.domain == self.domain_name and m.key not in self.not_found
        }
        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['all_blobs'](self.domain_name)
            exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(expected, set(tgzfile.getnames()))

    def test_migrate_multimedia(self):
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images',
                                  'commcare-hq-logo.png')
        with open(image_path, 'rb') as f:
            image_data = f.read()

        files = (
            (CommCareImage, self.domain_name, image_data),
            (CommCareAudio, self.domain_name, b'fake audio'),
            (CommCareVideo, self.domain_name, b'fake video'),
            (CommCareAudio, 'other_domain', b'fake audio 1'),
        )

        blob_keys = []
        for doc_class, domain, data in files:
            obj = doc_class.get_by_data(data)
            obj.attach_data(data)
            obj.add_domain(domain)
            self.addCleanup(obj.delete)
            self.assertEqual(data, obj.get_display_file(False))
            blob_keys.append(obj.blobs[obj.attachment_id].key)

        expected = set(blob_keys[:-1])
        with NamedTemporaryFile() as out:
            exporter = EXPORTERS['multimedia'](self.domain_name)
            exporter.migrate(out.name, force=True)
            with tarfile.open(out.name, 'r:gz') as tgzfile:
                self.assertEqual(expected, set(tgzfile.getnames()))
