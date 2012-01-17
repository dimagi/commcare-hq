from PIL import Image
from datetime import datetime
import hashlib
from couchdbkit.ext.django.schema import *
from hutch.models import AuxMedia, AttachmentImage

class HQMediaType(object):
    IMAGE = 0
    AUDIO = 1
    names = ["image", "audio"]

class CommCareMultimedia(Document):

    file_hash = StringProperty()
    aux_media = SchemaListProperty(AuxMedia)
    tags = StringListProperty()
    last_modified = DateTimeProperty()
    valid_domains = StringListProperty()

    def attach_data(self, data, filename, upload_path=None, username=None):
        self.last_modified = datetime.utcnow()
        self.save()
        Image.new(data)
        if not filename in self.current_attachments:
            self.put_attachment(data, filename)
            new_media = AuxMedia()
            new_media.uploaded_date = datetime.utcnow()
            new_media.attachment_id = filename
            new_media.uploaded_filename = upload_path
            new_media.uploaded_by = username
            new_media.checksum = self.file_hash
            self.aux_media.append(new_media)
        self.save()

    def add_domain(self, domain):
        if domain not in self.valid_domains:
            self.valid_domains.append(domain)
            self.save()

    @property
    def current_attachments(self):
        return [aux.attachment_id for aux in self.aux_media]
        
    @classmethod
    def generate_hash(cls, data):
        return hashlib.md5(data).hexdigest()

    @classmethod
    def get_by_hash(cls, file_hash):
        result = cls.view('hqmedia/by_hash', key=file_hash, include_docs=True).one()
        if not result:
            result = cls()
            result.file_hash = file_hash
        return result

    @classmethod
    def get_by_data(cls, data):
        file_hash = cls.generate_hash(data)
        media = cls.get_by_hash(file_hash)
        return media


class CommCareImage(CommCareMultimedia):
    pass

class CommCareAudio(CommCareMultimedia):
    pass

class HQMediaMapItem(DocumentSchema):

    multimedia_id = StringProperty()
    media_type = StringProperty()
    output_size = DictProperty()

class HQMediaMixin(Document):

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(HQMediaMapItem)

    def create_mapping(self, multimedia, filename, form_path):
        map_item = HQMediaMapItem()
        map_item.multimedia_id = multimedia._id
        map_item.media_type = multimedia.doc_type
        self.multimedia_map[form_path] = map_item
        self.save()