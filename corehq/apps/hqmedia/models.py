from StringIO import StringIO
from PIL import Image
from datetime import datetime
import hashlib
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from couchdbkit.ext.django.schema import *
from django.core.urlresolvers import reverse
import magic
from hutch.models import AuxMedia, AttachmentImage, MediaAttachmentManager
from corehq.apps import domain
from corehq.apps.domain.models import LICENSES
from dimagi.utils.couch.database import get_db

class HQMediaType(object):
    IMAGE = 0
    AUDIO = 1
    names = ["image", "audio"]

class HQMediaLicense(DocumentSchema):
    domain = StringProperty()
    author = StringProperty()
    organization = StringProperty()
    type = StringProperty(choices=LICENSES)

    @property
    def display_name(self):
        return LICENSES.get(self.type, "Improper License")

class CommCareMultimedia(Document):
    file_hash = StringProperty()
    aux_media = SchemaListProperty(AuxMedia)

    last_modified = DateTimeProperty()
    valid_domains = StringListProperty() # appears to be mostly unused as well - timbauman
    # add something about context from the form(s) its in

    owners = StringListProperty(default=[])
    licenses = SchemaListProperty(HQMediaLicense, default=[])
    shared_by = StringListProperty(default=[])
    tags = DictProperty(default={}) # dict of string lists

    @classmethod
    def wrap(cls, data):
        if data.get('tags') == []:
            data['tags'] = {}
        if not data.get('owners'):
            data['owners'] = data.get('valid_domains', [])
        if isinstance(data.get('licenses', ''), dict):
            # need to migrate licncses from old format to new format
            # old: {"mydomain": "public", "yourdomain": "cc"}
            migrated = [HQMediaLicense(domain=domain, type=type)._doc \
                        for domain, type in data["licenses"].items()]
            data['licenses'] = migrated
        return super(CommCareMultimedia, cls).wrap(data)

    def attach_data(self, data, upload_path=None, username=None, attachment_id=None,
                    media_meta=None, replace_attachment=False):
        self.last_modified = datetime.utcnow()
        self.save()
        if not attachment_id:
            attachment_id = self.file_hash
        if attachment_id in self.current_attachments and replace_attachment:
            self.delete_attachment(attachment_id)
            for aux in self.aux_media:
                if aux.attachment_id == attachment_id:
                    self.aux_media.remove(aux)
            self.save()
        if not attachment_id in self.current_attachments:
            mime = magic.Magic(mime=True)
            content_type = mime.from_buffer(data)
            self.put_attachment(data, attachment_id, content_type=content_type)
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

    def add_domain(self, domain, owner=None, **kwargs):
        print owner
        print self.owners
        print self.valid_domains

        if len(self.owners) == 0:
            # this is intended to simulate migration--if it happens that a media file somehow gets no more owners
            # (which should be impossible) it will transfer ownership to all copiers... not necessarily a bad thing,
            # just something to be aware of
            self.owners = self.valid_domains

        if owner and domain not in self.owners:
            self.owners.append(domain)
        elif owner == False and domain in self.owners:
            self.owners.remove(domain)

        if domain in self.owners:
            shared = kwargs.get('shared', '')
            if shared and domain not in self.shared_by:
                self.shared_by.append(domain)
            elif not shared and shared != '' and domain in self.shared_by:
                self.shared_by.remove(domain)

            if kwargs.get('tags', ''):
                self.tags[domain] = kwargs['tags']

        if domain not in self.valid_domains:
            self.valid_domains.append(domain)
        self.save()

    def get_display_file(self, return_type=True):
        all_ids = self.current_attachments
        if all_ids:
            first_id = all_ids[0]
            data = self.fetch_attachment(first_id, True).read()
            if return_type:
                content_type =  self._attachments[first_id]['content_type']
                return data, content_type
            else:
                return data
        return None

    @property
    def current_attachments(self):
        return [aux.attachment_id for aux in self.aux_media]

    @property
    def valid_content_types(self):
        return ['image/jpeg', 'image/png', 'audio/mpeg', 'image/gif', 'image/bmp']
        
    @classmethod
    def generate_hash(cls, data):
        return hashlib.md5(data).hexdigest()

    @classmethod
    def get_by_hash(cls, file_hash):
        result = cls.view('hqmedia/by_hash', key=file_hash, include_docs=True).first()
        if not result:
            result = cls()
            result.file_hash = file_hash
        return result

    @classmethod
    def get_by_data(cls, data):
        file_hash = cls.generate_hash(data)
        media = cls.get_by_hash(file_hash)
        media.save()
        return media

    @classmethod
    def validate_content_type(cls, content_type):
        return True

    @classmethod
    def get_all(cls):
        return cls.view('hqmedia/by_doc_type', key=cls.__name__, include_docs=True)

    @classmethod
    def all_tags(cls):
        return [d['key'] for d in cls.view('hqmedia/tags', group=True).all()]

    def url(self):
        return reverse("hqmedia_download", args=[self.doc_type,
                                                 self._id])

    @property
    def is_shared(self):
        return len(self.shared_by) > 0

    @classmethod
    def search(cls, query, limit=10):
        results = get_db().search(cls.Config.search_view, q=query, limit=limit, stale='ok')
        return map(cls.get, [r['id'] for r in results])

    @property
    def license(self):
        return self.licenses[0] if self.licenses else None

    def update_or_add_license(self, domain, type="", author="", org=""):
        for license in self.licenses:
            if license.domain == domain:
                license.type = type or license.type
                license.author = author or license.author
                license.organization = org or license.organization
                break
        else:
            print type
            print author
            license = HQMediaLicense(domain=domain, type=type, author=author, organization=org)
            self.licenses.append(license)

        self.save()

class CommCareImage(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/image_search'

    def attach_data(self, data, upload_path=None, username=None, attachment_id=None, media_meta=None, replace_attachment=False):
        image = Image.open(StringIO(data))
        attachment_id = "%dx%d" % image.size
        attachment_id = "%s-%s.%s" % (self.file_hash, attachment_id, image.format)
        if not media_meta:
            media_meta = {}
        media_meta["size"] = {
            "width": image.size[0],
            "height": image.size[1]
        }
        super(CommCareImage, self).attach_data(data, upload_path, username, attachment_id, media_meta, replace_attachment)

    @classmethod
    def validate_content_type(cls, content_type):
        return content_type in ['image/jpeg', 'image/png', 'image/gif', 'image/bmp']

        
class CommCareAudio(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/audio_search'

    @classmethod
    def validate_content_type(cls, content_type):
        return content_type in ['audio/mpeg', 'audio/mp3']



class HQMediaMapItem(DocumentSchema):

    multimedia_id = StringProperty()
    media_type = StringProperty()
    output_size = DictProperty()

    @staticmethod
    def format_match_map(path, media_type=None, media_id=None, upload_path=""):
        return {
            "path": path,
            "uid": path.replace('jr://','').replace('/', '_').replace('.', '_'),
            "m_id": media_id if media_id else "",
            "url": reverse("hqmedia_download", args=[media_type, media_id]) if media_id else "",
            "upload_path": upload_path
        }

class HQMediaMixin(Document):

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(HQMediaMapItem)

    def create_mapping(self, multimedia, form_path):
        form_path = form_path.strip()
        map_item = HQMediaMapItem()
        map_item.multimedia_id = multimedia._id
        map_item.media_type = multimedia.doc_type
        self.multimedia_map[form_path] = map_item

        try:
            self.save()
        except ResourceConflict:
            # Attempt to fetch the document again.
            updated_doc = self.get(self._id)
            updated_doc.create_mapping(multimedia, form_path)

    def get_media_documents(self):
        for form_path, map_item in self.multimedia_map.items():
            media = eval(map_item.media_type)
            try:
                media = media.get(map_item.multimedia_id)
            except ResourceNotFound:
                media = None
            yield form_path, media

    def get_template_map(self, sorted_files):
        product = []
        missing_refs = 0
        multimedia_map = self.multimedia_map
        for f in sorted_files:
            try:
                f = f.strip()
                product.append(HQMediaMapItem.format_match_map(f,
                                                            multimedia_map[f].media_type,
                                                            multimedia_map[f].multimedia_id))
            except KeyError:
                product.append(HQMediaMapItem.format_match_map(f))
                missing_refs += 1
            except AttributeError:
                pass
        return product, missing_refs

    def clean_mapping(self, user=None):
        for path, media in self.get_media_documents():
            if not media or (not media.is_shared and self.domain not in media.owners):
                del self.multimedia_map[path]
