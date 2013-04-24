from StringIO import StringIO
import mimetypes
from PIL import Image
from datetime import datetime
import hashlib
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from couchdbkit.ext.django.schema import *
from couchdbkit.schema import LazyDict
from django.contrib import messages
from django.core.urlresolvers import reverse
import logging
import magic
from corehq.apps.app_manager.xform import XFormValidationError
from couchforms.models import XFormError
from dimagi.utils.decorators.memoized import memoized
from hutch.models import AuxMedia
from corehq.apps.domain.models import LICENSES
from dimagi.utils.couch.database import get_db
from django.utils.translation import ugettext as _

MULTIMEDIA_PREFIX = "jr://file/"


class HQMediaLicense(DocumentSchema):
    domain = StringProperty()
    author = StringProperty()
    organization = StringProperty()
    type = StringProperty(choices=LICENSES)
    attribution_notes = StringProperty()

    def __init__(self, _d=None, **properties):
        # another place we have to lazy migrate
        if properties and properties.get('type', '') == 'public':
            properties['type'] = 'cc'
        super(HQMediaLicense, self).__init__(_d, **properties)
    
    @property
    def display_name(self):
        return LICENSES.get(self.type, "Improper License")


class CommCareMultimedia(Document):
    """
        The base object of all CommCare Multimedia
    """
    file_hash = StringProperty()  # use this to search for multimedia in couch
    aux_media = SchemaListProperty(AuxMedia)

    last_modified = DateTimeProperty()
    valid_domains = StringListProperty() # appears to be mostly unused as well - timbauman
    # add something about context from the form(s) its in

    owners = StringListProperty(default=[])
    licenses = SchemaListProperty(HQMediaLicense, default=[])
    shared_by = StringListProperty(default=[])
    tags = DictProperty(default={})  # dict of string lists

    @property
    def is_shared(self):
        return len(self.shared_by) > 0

    @property
    def license(self):
        return self.licenses[0] if self.licenses else None

    def update_or_add_license(self, domain, type="", author="", attribution_notes="", org=""):
        for license in self.licenses:
            if license.domain == domain:
                license.type = type or license.type
                license.author = author or license.author
                license.organization = org or license.organization
                license.attribution_notes = attribution_notes or license.attribution_notes
                break
        else:
            license = HQMediaLicense(   domain=domain, type=type, author=author,
                                        attribution_notes=attribution_notes, organization=org)
            self.licenses.append(license)

        self.save()

    def url(self):
        return reverse("hqmedia_download", args=[self.doc_type, self._id])

    def attach_data(self, data, original_filename=None, username=None, attachment_id=None,
                    media_meta=None, replace_attachment=False):
        """
            This creates the auxmedia attachment with the downloaded data.
        """
        self.last_modified = datetime.utcnow()
        is_update = False

        if not attachment_id:
            attachment_id = self.file_hash

        if (attachment_id in self.current_attachments) and replace_attachment:
            self.delete_attachment(attachment_id)
            for aux in self.aux_media:
                if aux.attachment_id == attachment_id:
                    self.aux_media.remove(aux)

        if not attachment_id in self.current_attachments:
            if not getattr(self, '_id'):
                self.save()  # let's just make sure an id has been assigned to this guy before we try to put_attachment
            self.put_attachment(data, attachment_id, content_type=self.get_mime_type(data, filename=original_filename))
            new_media = AuxMedia()
            new_media.uploaded_date = datetime.utcnow()
            new_media.attachment_id = attachment_id
            new_media.uploaded_filename = original_filename
            new_media.uploaded_by = username
            new_media.checksum = self.file_hash
            if media_meta:
                new_media.media_meta = media_meta
            self.aux_media.append(new_media)
            self.save()
            is_update = True

        return is_update

    def add_domain(self, domain, owner=None, **kwargs):
        if len(self.owners) == 0:
            # this is intended to simulate migration--if it happens that a media file somehow gets no more owners
            # (which should be impossible) it will transfer ownership to all copiers... not necessarily a bad thing,
            # just something to be aware of
            self.owners = self.valid_domains

        if owner and domain not in self.owners:
            self.owners.append(domain)
        elif not owner and domain in self.owners:
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
                content_type = self._attachments[first_id]['content_type']
                return data, content_type
            else:
                return data
        return None

    def get_media_info(self, path, is_updated=False, original_path=None):
        return {
            "path": path,
            "uid": self.file_hash,
            "m_id": self._id,
            "url": reverse("hqmedia_download", args=[self.__class__.__name__, self._id]),
            "updated": is_updated,
            "original_path": original_path,
            "icon_class": self.get_icon_class(),
        }

    @property
    def current_attachments(self):
        return [aux.attachment_id for aux in self.aux_media]

    @classmethod
    def get_mime_type(cls, data, filename=None):
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(data)
        if mime_type.startswith('application') and filename is not None:
            guessed_type = mimetypes.guess_type(filename)
            mime_type = guessed_type[0] if guessed_type[0] else mime_type
        return mime_type

    @classmethod
    def get_base_mime_type(cls, data, filename=None):
        mime_type = cls.get_mime_type(data, filename=filename)
        return mime_type.split('/')[0] if mime_type else None
        
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
        return cls.get_by_hash(file_hash)

    @classmethod
    def get_all(cls):
        return cls.view('hqmedia/by_doc_type', key=cls.__name__, include_docs=True)

    @classmethod
    def all_tags(cls):
        return [d['key'] for d in cls.view('hqmedia/tags', group=True).all()]

    @classmethod
    def search(cls, query, limit=10):
        results = get_db().search(cls.Config.search_view, q=query, limit=limit, stale='ok')
        return map(cls.get, [r['id'] for r in results])

    @classmethod
    def get_doc_class(cls, doc_type):
        return {
            'CommCareImage': CommCareImage,
            'CommCareAudio': CommCareAudio,
            'CommCareVideo': CommCareVideo,
        }[doc_type]

    @classmethod
    def get_class_by_data(cls, data, filename=None):
        return {
            'image': CommCareImage,
            'audio': CommCareAudio,
            'video': CommCareVideo,
        }.get(cls.get_base_mime_type(data, filename=filename))

    @classmethod
    def get_form_path(cls, path):
        path = path.strip().lower()
        if path.startswith(MULTIMEDIA_PREFIX):
            return path
        if path.startswith('/'):
            path = path[1:]
        return "%s%s" % (MULTIMEDIA_PREFIX, path)

    @classmethod
    def get_standard_path(cls, path):
        return path.replace(MULTIMEDIA_PREFIX, "")

    @classmethod
    def wrap(cls, data):
        should_save = False
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

        # deprecating support for public domain license
        if isinstance(data.get("licenses", ""), list) and len(data["licenses"]) > 0:
            if data["licenses"][0].get("type", "") == "public":
                data["licenses"][0]["type"] = "cc"
                should_save = True
        self = super(CommCareMultimedia, cls).wrap(data)
        if should_save:
            self.save()
        return self

    @classmethod
    def get_nice_name(cls):
        return _("Generic Multimedia")

    @classmethod
    def get_icon_class(cls):
        raise NotImplementedError("Please specify an icon class.")


class CommCareImage(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/image_search'

    @memoized
    def get_image_object(self, data):
        return Image.open(StringIO(data))

    def get_thumbnail_data(self, data, size):
        try:
            image = self.get_image_object(data)
            if image.mode != "RGB":
                image = image.convert("RGB")
            o = StringIO()
            image.thumbnail(size, Image.ANTIALIAS)
            image.save(o, format="JPEG")
            return o.getvalue()
        except ImportError:
            logging.error("Could not correctly process thumbnail for media %s" % self._id)
        return data

    def attach_data(self, data, original_filename=None, username=None, attachment_id=None, media_meta=None,
                    replace_attachment=False):
        image = self.get_image_object(data)
        attachment_id = "%dx%d" % image.size
        attachment_id = "%s-%s.%s" % (self.file_hash, attachment_id, image.format)
        if not media_meta:
            media_meta = {}
        media_meta["size"] = {
            "width": image.size[0],
            "height": image.size[1]
        }
        return super(CommCareImage, self).attach_data(data, original_filename=original_filename, username=username,
                                                      attachment_id=attachment_id, media_meta=media_meta,
                                                      replace_attachment=replace_attachment)

    @classmethod
    def get_nice_name(cls):
        return _("Image")

    @classmethod
    def get_icon_class(cls):
        return "icon-picture"

        
class CommCareAudio(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/audio_search'

    @classmethod
    def get_nice_name(cls):
        return _("Audio")

    @classmethod
    def get_icon_class(cls):
        return "icon-volume-up"


class CommCareVideo(CommCareMultimedia):

    @classmethod
    def get_nice_name(cls):
        return _("Video")

    @classmethod
    def get_icon_class(cls):
        return "icon-facetime-video"


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


class ApplicationMediaReference(object):
    """
        Generated when all_media is queried and stored in memory.

        Contains all the information needed to know where / how this the media PATH is stored in the application.
        Provides no link to a multimedia object---link comes from the application's multimedia map.
        Useful info for user-facing things.
    """

    def __init__(self, path,
                 module_id=None, module_name=None,
                 form_id=None, form_name=None, form_order=None,
                 media_type=None, is_menu_media=False):

        if not isinstance(path, basestring):
            raise ValueError("path should be a string")
        self.path = path.strip()

        if not issubclass(media_type, CommCareMultimedia):
            raise ValueError("media_type should be a type of CommCareMultimedia")

        self.module_id = module_id
        self.module_name = module_name

        self.form_id = form_id
        self.form_name = form_name
        self.form_order = form_order

        self.media_type = media_type
        self.is_menu_media = is_menu_media

    def __str__(self):
        detailed_location = ""
        if self.module_name:
            detailed_location = " | %s" % self.get_module_name()
        if self.form_name:
            detailed_location = "%s > %s" % (detailed_location, self.get_form_name())
        return "%(media_type)s at %(path)s%(detailed_location)s" % {
            'media_type': self.media_type.__name__,
            'path': self.path,
            'detailed_location': detailed_location,
        }

    def as_json(self, lang=None):
        return {
            'module': {
                'name': self.get_module_name(lang),
                'id': self.module_id,
            },
            'form': {
                'name': self.get_form_name(lang),
                'id': self.form_id,
                'order': self.form_order,
            },
            'is_menu_media': self.is_menu_media,
            'media_class': self.media_type.__name__,
            'path': self.path,
            "icon_class": self.media_type.get_icon_class(),
        }

    def _get_name(self, raw_name, lang=None):
        if raw_name is None:
            return ""
        if not isinstance(raw_name, dict) or not isinstance(raw_name, LazyDict):
            return raw_name
        if lang is None:
            lang = 'en'
        return raw_name.get(lang)

    def get_module_name(self, lang=None):
        return self._get_name(self.module_name, lang=lang)

    def get_form_name(self, lang=None):
        return self._get_name(self.form_name, lang=lang)


class HQMediaMixin(Document):
    """
        Mix this guy in with Application to support multimedia.
        Anything multimedia related happens here.
    """

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(HQMediaMapItem)

    @property
    @memoized
    def all_media(self):
        """
            Get all the paths of multimedia IMAGES and AUDIO referenced in this application.
            (Video and anything else is currently not supported...)
        """
        media = []
        self.media_form_errors = False

        def _add_menu_media(item, **kwargs):
            if item.media_image:
                media.append(ApplicationMediaReference(item.media_image,
                                                       media_type=CommCareImage,
                                                       is_menu_media=True, **kwargs))
            if item.media_audio:
                media.append(ApplicationMediaReference(item.media_audio,
                                                       media_type=CommCareAudio,
                                                       is_menu_media=True, **kwargs))

        for m, module in enumerate(self.get_modules()):
            media_kwargs = {
                'module_name': module.name,
                'module_id': m,
            }
            _add_menu_media(module, **media_kwargs)
            for f_order, f in enumerate(module.get_forms()):
                media_kwargs['form_name'] = f.name
                media_kwargs['form_id'] = f.unique_id
                media_kwargs['form_order'] = f_order
                _add_menu_media(f, **media_kwargs)
                try:
                    parsed = f.wrapped_xform()
                    if not parsed.exists():
                        continue
                    f.validate_form()
                    for image in parsed.image_references:
                        if image:
                            media.append(ApplicationMediaReference(image, media_type=CommCareImage, **media_kwargs))
                    for audio in parsed.audio_references:
                        if audio:
                            media.append(ApplicationMediaReference(audio, media_type=CommCareAudio, **media_kwargs))
                except (XFormValidationError, XFormError):
                    self.media_form_errors = True
        return media

    @property
    @memoized
    def all_media_paths(self):
        return set([m.path for m in self.all_media])

    @memoized
    def get_all_paths_of_type(self, media_type_name):
        return set([m.path for m in self.all_media if m.media_type.__name__ == media_type_name])

    def remove_unused_mappings(self):
        """
            This checks to see if the paths specified in the multimedia map still exist in the Application.
            If not, then that item is removed from the multimedia map.
        """
        map_changed = False
        for path in self.multimedia_map.keys():
            if path not in self.all_media_paths:
                map_changed = True
                del self.multimedia_map[path]
        if map_changed:
            self.save()

    def create_mapping(self, multimedia, form_path):
        """
            This creates the mapping of a path to the multimedia in an application to the media object stored in couch.
        """
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

    def get_media_objects(self):
        """
            Gets all the media objects stored in the multimedia map.
        """
        for path, map_item in self.multimedia_map.items():
            media = CommCareMultimedia.get_doc_class(map_item.media_type)
            try:
                media = media.get(map_item.multimedia_id)
                yield path, media
            except ResourceNotFound:
                # delete media reference from multimedia map so this doesn't pop up again!
                del self.multimedia_map[path]
                self.save()

    def get_references(self, lang=None):
        """
            Used for the multimedia controller.
        """
        return [m.as_json(lang) for m in self.all_media]

    def get_object_map(self):
        object_map = {}
        for path, media_obj in self.get_media_objects():
            object_map[path] = media_obj.get_media_info(path)
        return object_map

    def get_reference_totals(self):
        """
            Returns a list of totals of each type of media in the application and total matches.
        """
        totals = []
        for mm in [CommCareImage, CommCareAudio]:
            paths = self.get_all_paths_of_type(mm.__name__)
            if len(paths) > 0:
                totals.append({
                        'media_type': mm.get_nice_name(),
                        'totals': len(paths),
                        'matched': len([p for p in self.multimedia_map.keys() if p in paths]),
                        'icon_class': mm.get_icon_class(),
                })
        return totals

    def prepare_multimedia_for_exchange(self):
        """
            Prepares the multimedia in the application for exchanging across domains.
        """
        self.remove_unused_mappings()
        for path, media in self.get_media_objects():
            if not media or (not media.is_shared and self.domain not in media.owners):
                del self.multimedia_map[path]

    def get_media_references(self, request=None):
        """
            DEPRECATED METHOD: Use self.all_media instead.
            Use this to check all Application media against the stored multimedia_map.
        """
        #todo this should get updated to use self.all_media
        from corehq.apps.app_manager.models import Application
        if not isinstance(self, Application):
            raise NotImplementedError("Sorry, this method is only supported for CommCare HQ Applications.")

        from corehq.apps.hqmedia.utils import get_application_media
        all_media, form_errors = get_application_media(self)

        # Because couchdbkit is terrible?
        multimedia_map = self.multimedia_map

        missing_refs = False

        references = {}
        for section, media in all_media.items():
            references[section] = {}
            for media_type, paths in media.items():
                maps = []
                missing = 0
                matched = 0
                errors = 0
                for path in paths:
                    match_map = None
                    try:
                        media_item = multimedia_map[path]
                        match_map = HQMediaMapItem.format_match_map(path,
                            media_item.media_type, media_item.multimedia_id)
                        matched += 1
                    except KeyError:
                        match_map = HQMediaMapItem.format_match_map(path)
                        missing += 1
                    except AttributeError:
                        errors += 1
                        if request:
                            messages.error(request, _("Encountered an AttributeError for media: %s" % path))
                    except UnicodeEncodeError:
                        errors += 1
                        if request:
                            messages.error(request, _("This application has unsupported text in one "
                                                      "of it's media file label fields: %s" % path))
                    if match_map:
                        maps.append(match_map)
                    if errors > 0 or missing > 0:
                        missing_refs = True

                references[section][media_type] = {
                    'maps': maps,
                    'missing': missing,
                    'matched': matched,
                    'errors': errors,
                }

        return {
            "references": references,
            "form_errors": form_errors,
            "missing_refs": missing_refs,
        }
