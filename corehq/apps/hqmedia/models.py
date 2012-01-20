from StringIO import StringIO
from PIL import Image
from datetime import datetime
import hashlib
from couchdbkit.ext.django.schema import *
from hutch.models import AuxMedia, AttachmentImage, MediaAttachmentManager

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

    def attach_data(self, data, upload_path=None, username=None, attachment_id=None, media_meta=None):
        self.last_modified = datetime.utcnow()
        self.save()
        if not attachment_id:
            attachment_id = self.file_hash
        if not attachment_id in self.current_attachments:
            self.put_attachment(data, attachment_id)
            new_media = AuxMedia()
            new_media.uploaded_date = datetime.utcnow()
            new_media.attachment_id = attachment_id
            new_media.uploaded_filename = upload_path
            new_media.uploaded_by = username
            new_media.checksum = self.file_hash
            if media_meta:
                new_media.media_meta = media_meta
            self.aux_media.append(new_media)
        self.save()

    def add_domain(self, domain):
        if domain not in self.valid_domains:
            self.valid_domains.append(domain)
            self.save()

    def get_display_file(self, return_type=True):
        all_ids = self.current_attachments
        if all_ids:
            first_id = all_ids[0]
            data = self.fetch_attachment(first_id)
            if return_type:
                content_type =  self._attachments[first_id]['content_type']
                return data, content_type
            else:
                return data
        return None

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

    def attach_data(self, data, upload_path=None, username=None, attachment_id=None, media_meta=None):
        image = Image.open(StringIO(data))
        attachment_id = "%dx%d" % image.size
        attachment_id = "%s-%s.%s" % (self.file_hash, attachment_id, image.format)
        media_meta = {
                "size": {
                    "width": image.size[0],
                    "height": image.size[1]
                }
            }
        super(CommCareImage, self).attach_data(data, upload_path, username, attachment_id, media_meta)
        
class CommCareAudio(CommCareMultimedia):
    pass

class HQMediaMapItem(DocumentSchema):

    multimedia_id = StringProperty()
    media_type = StringProperty()
    output_size = DictProperty()

class HQMediaMixin(Document):

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(HQMediaMapItem)

    def create_mapping(self, multimedia, form_path):
        form_path = form_path.strip()
        map_item = HQMediaMapItem()
        map_item.multimedia_id = multimedia._id
        map_item.media_type = multimedia.doc_type
        self.multimedia_map[form_path] = map_item
        self.save()

    def get_map_display_data(self):
        for form_path, map_item in self.multimedia_map.items():
            media = eval(map_item.media_type)
            media = media.get(map_item.multimedia_id)
            print media.file_hash