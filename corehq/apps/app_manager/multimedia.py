from datetime import datetime
from couchdbkit.ext.django.schema import *
from hutch.models import AuxMedia, AttachmentImage

class CommCareMediaType(object):
    IMAGE = 0
    AUDIO = 1
    names = ["Image", "Audio"]

class CommCareMultimedia(Document):

    md5_hash = StringProperty()
    aux_media = SchemaListProperty(AuxMedia)
    tags = StringListProperty()

    def attach_media(self, content, upload_user_id=None, name=None, content_type=None, content_length=None):
        self.put_attachment(content, name, content_type, content_length)
        new_media = AuxMedia()
        new_media.uploaded_by = upload_user_id
        new_media.uploaded_date = datetime.utcnow()
        new_media.attachment_id = name
        self.aux_media.append(new_media)

class CommCareMultimediaMapItem(DocumentSchema):
    
    multimedia_id = StringProperty()
    attachment_name = StringProperty()
    media_type = StringProperty()
    output_size = DictProperty()

class MultimediaMixin(Document):

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(CommCareMultimediaMapItem)