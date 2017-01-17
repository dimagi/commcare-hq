import hashlib
import logging
import mimetypes
from datetime import datetime
from StringIO import StringIO

import magic
from couchdbkit.exceptions import ResourceConflict
from django.template.defaultfilters import filesizeformat

from dimagi.ext.couchdbkit import *
from dimagi.utils.couch.database import get_safe_read_kwargs, iter_docs
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.decorators.memoized import memoized
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from PIL import Image

from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.xform import XFormValidationError
from corehq.apps.domain.models import LICENSES, LICENSE_LINKS
from corehq.blobs.mixin import BlobMixin

MULTIMEDIA_PREFIX = "jr://file/"
LOGO_ARCHIVE_KEY = 'logos'


class AuxMedia(DocumentSchema):
    """
    Additional metadata companion for couch models
    that you want to add arbitrary attachments to
    """
    uploaded_date = DateTimeProperty()
    uploaded_by = StringProperty()
    uploaded_filename = StringProperty()  # the uploaded filename info
    checksum = StringProperty()
    attachment_id = StringProperty()  # the actual attachment id in blobs
    media_meta = DictProperty()
    notes = StringProperty()


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

    @property
    def deed_link(self):
        return LICENSE_LINKS.get(self.type)


class CommCareMultimedia(BlobMixin, SafeSaveDocument):
    """
    The base object of all CommCare Multimedia
    """
    file_hash = StringProperty()  # use this to search for multimedia in couch
    aux_media = SchemaListProperty(AuxMedia)

    last_modified = DateTimeProperty()
    valid_domains = StringListProperty()  # A list of domains that uses this file
    owners = StringListProperty(default=[])  # list of domains that uploaded this file
    licenses = SchemaListProperty(HQMediaLicense, default=[])
    shared_by = StringListProperty(default=[])  # list of domains that can share this file
    tags = DictProperty(default={})  # dict of string lists

    @classmethod
    def get(cls, docid, rev=None, db=None, dynamic_properties=True):
        # copied and tweaked from the superclass's method
        if not db:
            db = cls.get_db()
        cls._allow_dynamic_properties = dynamic_properties
        # on cloudant don't get the doc back until all nodes agree
        # on the copy, to avoid race conditions
        extras = get_safe_read_kwargs()
        return db.get(docid, rev=rev, wrapper=cls.wrap, **extras)

    @property
    def is_shared(self):
        return len(self.shared_by) > 0

    @property
    def license(self):
        return self.licenses[0] if self.licenses else None

    @retry_resource(3)
    def update_or_add_license(self, domain, type="", author="", attribution_notes="", org="", should_save=True):
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

        if should_save:
            self.save()

    def url(self):
        return reverse("hqmedia_download", args=[self.doc_type, self._id])

    def attach_data(self, data, original_filename=None, username=None, attachment_id=None,
                    media_meta=None):
        """
        This creates the auxmedia attachment with the downloaded data.
        """
        self.last_modified = datetime.utcnow()

        if not attachment_id:
            attachment_id = self.file_hash

        if not self.blobs or attachment_id not in self.blobs:
            if not getattr(self, '_id'):
                # put attchment blows away existing data, so make sure an id has been
                # assigned to this guy before we do it. this is the expected path
                self.save()
            else:
                # this should only be files that had attachments deleted while the bug
                # was in effect, so hopefully we will stop seeing it after a few days
                logging.error('someone is uploading a file that should have existed for multimedia %s' % self._id)
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
        return True

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
        if self.attachment_id:
            data = self.fetch_attachment(self.attachment_id, stream=True).read()
            if return_type:
                content_type = self.blobs[self.attachment_id].content_type
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
            "media_type": self.get_nice_name(),
            "humanized_content_length": filesizeformat(self.content_length),
        }

    @property
    def attachment_id(self):
        if not self.aux_media:
            return None
        ids = set([aux.attachment_id for aux in self.aux_media])
        assert len(ids) == 1
        return ids.pop()

    @property
    def content_length(self):
        if self.attachment_id:
            return self.blobs[self.attachment_id].content_length

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
    def get_doc_class(cls, doc_type):
        return {
            'CommCareImage': CommCareImage,
            'CommCareAudio': CommCareAudio,
            'CommCareVideo': CommCareVideo,
            'CommCareMultimedia': CommCareMultimedia,
        }[doc_type]

    @classmethod
    def get_class_by_data(cls, data, filename=None):
        return {
            'image': CommCareImage,
            'audio': CommCareAudio,
            'video': CommCareVideo,
        }.get(cls.get_base_mime_type(data, filename=filename))

    @classmethod
    def get_form_path(cls, path, lowercase=False):
        path = path.strip()
        if lowercase:
            path = path.lower()
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
        return "fa fa-desktop"


class ImageThumbnailError(Exception):
    pass


class CommCareImage(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/image_search'

    def attach_data(self, data, original_filename=None, username=None, attachment_id=None, media_meta=None):
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
                                                      attachment_id=attachment_id, media_meta=media_meta)

    def get_media_info(self, path, is_updated=False, original_path=None):
        info = super(CommCareImage, self).get_media_info(path, is_updated=is_updated, original_path=original_path)
        info['image_size'] = self.image_size_display()
        return info

    def image_size_display(self):
        for aux_media in self.aux_media:
            image_size = aux_media.media_meta.get('size', {})
            width = image_size.get('width')
            height = image_size.get('height')
            if width is not None and height is not None:
                return "{} X {} Pixels".format(width, height)

    @classmethod
    def get_image_object(cls, data):
        return Image.open(StringIO(data))

    @classmethod
    def _get_resized_image(cls, image, size):
        if image.mode not in ["RGB", "RGBA"]:
            image = image.convert("RGB")
        o = StringIO()
        try:
            image.thumbnail(size, Image.ANTIALIAS)
        except IndexError:
            raise ImageThumbnailError()
        image.save(o, format="PNG")
        return o.getvalue()

    @classmethod
    def get_invalid_image_data(cls):
        import os
        invalid_image_path = os.path.join(os.path.dirname(__file__), 'static/hqmedia/images/invalid_image.png')
        return Image.open(open(invalid_image_path))

    @classmethod
    def get_thumbnail_data(cls, data, size):
        try:
            data = cls._get_resized_image(cls.get_image_object(data), size)
        except (ImageThumbnailError, ImportError, IOError):
            data = cls._get_resized_image(cls.get_invalid_image_data(), size)
        return data

    @classmethod
    def get_nice_name(cls):
        return _("Image")

    @classmethod
    def get_icon_class(cls):
        return "fa fa-picture-o"

        
class CommCareAudio(CommCareMultimedia):

    class Config(object):
        search_view = 'hqmedia/audio_search'

    @classmethod
    def get_nice_name(cls):
        return _("Audio")

    @classmethod
    def get_icon_class(cls):
        return "fa fa-volume-up"


class CommCareVideo(CommCareMultimedia):

    @classmethod
    def get_nice_name(cls):
        return _("Video")

    @classmethod
    def get_icon_class(cls):
        return "fa fa-video-camera"


class HQMediaMapItem(DocumentSchema):

    multimedia_id = StringProperty()
    media_type = StringProperty()
    output_size = DictProperty()
    version = IntegerProperty()
    unique_id = StringProperty()
    form_media = BooleanProperty(default=False)

    @property
    def url(self):
        return reverse("hqmedia_download", args=[self.media_type, self.multimedia_id]) if self.multimedia_id else ""

    @classmethod
    def gen_unique_id(cls, m_id, path):
        return hashlib.md5("%s: %s" % (path.encode('utf-8'), str(m_id))).hexdigest()


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
                 media_class=None, is_menu_media=False, app_lang=None):

        if not isinstance(path, basestring):
            path = ''
        self.path = path.strip()

        if not issubclass(media_class, CommCareMultimedia):
            raise ValueError("media_class should be a type of CommCareMultimedia")

        self.module_id = module_id
        self.module_name = module_name

        self.form_id = form_id
        self.form_name = form_name
        self.form_order = form_order

        self.media_class = media_class
        self.is_menu_media = is_menu_media

        self.app_lang = app_lang or "en"

    def __str__(self):
        detailed_location = ""
        if self.module_name:
            detailed_location = " | %s" % self.get_module_name()
        if self.form_name:
            detailed_location = "%s > %s" % (detailed_location, self.get_form_name())
        return "%(media_class)s at %(path)s%(detailed_location)s" % {
            'media_class': self.media_class.__name__,
            'path': self.path,
            'detailed_location': detailed_location,
        }

    def as_dict(self, lang=None):
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
            'media_class': self.media_class.__name__,
            'path': self.path,
            "icon_class": self.media_class.get_icon_class(),
            "media_type": self.media_class.get_nice_name(),
        }

    def _get_name(self, raw_name, lang=None):
        if not raw_name:
            return ""
        if not isinstance(raw_name, dict):
            return raw_name
        if lang is None:
            lang = self.app_lang
        return raw_name.get(lang, raw_name.values()[0])

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

    # paths to custom logos
    logo_refs = DictProperty()

    archived_media = DictProperty()  # where we store references to the old logos (or other multimedia) on a downgrade, so that information is not lost

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
            media.extend([ApplicationMediaReference(image,
                                                    media_class=CommCareImage,
                                                    is_menu_media=True, **kwargs)
                          for image in item.all_image_paths()
                          if image])

            media.extend([ApplicationMediaReference(audio,
                                                    media_class=CommCareAudio,
                                                    is_menu_media=True, **kwargs)
                          for audio in item.all_audio_paths()
                          if audio])

        for m, module in enumerate(filter(lambda m: m.uses_media(), self.get_modules())):
            media_kwargs = {
                'module_name': module.name,
                'module_id': m,
                'app_lang': self.default_language,
            }
            _add_menu_media(module, **media_kwargs)

            for name, details, display in module.get_details():
                if display and details.display == 'short' and details.lookup_enabled and details.lookup_image:
                    media.append(ApplicationMediaReference(
                        details.lookup_image,
                        media_class=CommCareImage,
                        **media_kwargs)
                    )
                # Icons in case-details
                for column in details.get_columns():
                    if column.format == 'enum-image':
                        for map_item in column.enum:
                            # iterate over icons of each lang
                            icons = map_item.value.values()
                            media.extend([ApplicationMediaReference(
                                icon,
                                media_class=CommCareImage,
                                is_menu_media=True,
                                **media_kwargs)
                                for icon in icons
                                if icon]
                            )

            if module.case_list_form.form_id:
                _add_menu_media(module.case_list_form, **media_kwargs)

            if hasattr(module, 'case_list') and module.case_list.show:
                _add_menu_media(module.case_list, **media_kwargs)

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
                            media.append(ApplicationMediaReference(image, media_class=CommCareImage, **media_kwargs))
                    for audio in parsed.audio_references:
                        if audio:
                            media.append(ApplicationMediaReference(audio, media_class=CommCareAudio, **media_kwargs))
                    for video in parsed.video_references:
                        if video:
                            media.append(ApplicationMediaReference(video, media_class=CommCareVideo, **media_kwargs))
                    for text in parsed.text_references:
                        if text:
                            media.append(ApplicationMediaReference(text, media_class=CommCareMultimedia, **media_kwargs))
                except (XFormValidationError, XFormException):
                    self.media_form_errors = True
        return media

    def get_menu_media(self, module, module_index, form=None, form_index=None, to_language=None):
        if not module:
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(
            module, module_index, form=form, form_index=form_index,
            is_menu_media=True)
        media_kwargs.update(to_language=to_language or self.default_language)
        item = form or module
        return self._get_item_media(item, media_kwargs)

    def get_case_list_form_media(self, module, module_index, to_language=None):
        if not module:
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(module, module_index)
        media_kwargs.update(to_language=to_language or self.default_language)
        return self._get_item_media(module.case_list_form, media_kwargs)

    def get_case_list_menu_item_media(self, module, module_index, to_language=None):
        if not module or not module.uses_media() or not hasattr(module, 'case_list'):
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(module, module_index)
        media_kwargs.update(to_language=to_language or self.default_language)
        return self._get_item_media(module.case_list, media_kwargs)

    def get_case_list_lookup_image(self, module, module_index, type='case'):
        if not module:
            return {}
        media_kwargs = self.get_media_ref_kwargs(module, module_index)
        details_name = '{}_details'.format(type)
        if not hasattr(module, details_name):
            return {}

        image = ApplicationMediaReference(
            module[details_name].short.lookup_image,
            media_class=CommCareImage,
            **media_kwargs
        ).as_dict()
        return {
            'image': image
        }

    def _get_item_media(self, item, media_kwargs):
        menu_media = {}
        to_language = media_kwargs.pop('to_language', self.default_language)
        image_ref = ApplicationMediaReference(
            item.icon_by_language(to_language),
            media_class=CommCareImage,
            **media_kwargs
        )
        image_ref = image_ref.as_dict()
        menu_media['image'] = image_ref

        audio_ref = ApplicationMediaReference(
            item.audio_by_language(to_language),
            media_class=CommCareAudio,
            **media_kwargs
        )
        audio_ref = audio_ref.as_dict()
        menu_media['audio'] = audio_ref
        return menu_media

    @property
    @memoized
    def all_media_paths(self):
        return set([m.path for m in self.all_media])

    @memoized
    def get_all_paths_of_type(self, media_class_name):
        return set([m.path for m in self.all_media if m.media_class.__name__ == media_class_name])

    def get_media_ref_kwargs(self, module, module_index, form=None,
                             form_index=None, is_menu_media=False):
        return {
            'app_lang': self.default_language,
            'module_name': module.name,
            'module_id': module_index,
            'form_name': form.name if form else None,
            'form_id': form.unique_id if form else None,
            'form_order': form_index,
            'is_menu_media': is_menu_media,
        }

    @property
    @memoized
    def logo_paths(self):
        return set(value['path'] for value in self.logo_refs.values())

    def remove_unused_mappings(self):
        """
            This checks to see if the paths specified in the multimedia map still exist in the Application.
            If not, then that item is removed from the multimedia map.
        """
        map_changed = False
        paths = self.multimedia_map.keys() if self.multimedia_map else []
        permitted_paths = self.all_media_paths | self.logo_paths
        for path in paths:
            if path not in permitted_paths:
                map_changed = True
                del self.multimedia_map[path]
        if map_changed:
            self.save()

    def create_mapping(self, multimedia, form_path, save=True):
        """
            This creates the mapping of a path to the multimedia in an application to the media object stored in couch.
        """
        form_path = form_path.strip()
        map_item = HQMediaMapItem()
        map_item.multimedia_id = multimedia._id
        map_item.unique_id = HQMediaMapItem.gen_unique_id(map_item.multimedia_id, form_path)
        map_item.media_type = multimedia.doc_type
        self.multimedia_map[form_path] = map_item

        if save:
            try:
                self.save()
            except ResourceConflict:
                # Attempt to fetch the document again.
                updated_doc = self.get(self._id)
                updated_doc.create_mapping(multimedia, form_path)

    def get_media_objects(self, languages=None):
        """
            Gets all the media objects stored in the multimedia map.
            If passed a profile, will only get those that are used
            in a language in the profile.
        """
        found_missing_mm = False
        filter_multimedia = languages and self.media_language_map
        if filter_multimedia:
            requested_media = set()
            for lang in languages:
                requested_media.update(self.media_language_map[lang].media_refs)
        # preload all the docs to avoid excessive couch queries.
        # these will all be needed in memory anyway so this is ok.
        expected_ids = [map_item.multimedia_id for map_item in self.multimedia_map.values()]
        raw_docs = dict((d["_id"], d) for d in iter_docs(CommCareMultimedia.get_db(), expected_ids))
        for path, map_item in self.multimedia_map.items():
            if not filter_multimedia or not map_item.form_media or path in requested_media:
                media_item = raw_docs.get(map_item.multimedia_id)
                if media_item:
                    media_cls = CommCareMultimedia.get_doc_class(map_item.media_type)
                    yield path, media_cls.wrap(media_item)
                else:
                    # delete media reference from multimedia map so this doesn't pop up again!
                    del self.multimedia_map[path]
                    found_missing_mm = True
        if found_missing_mm:
            self.save()

    def get_references(self, lang=None):
        """
            Used for the multimedia controller.
        """
        return [m.as_dict(lang) for m in self.all_media]

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
        for mm in [CommCareImage, CommCareAudio, CommCareVideo]:
            paths = self.get_all_paths_of_type(mm.__name__)
            matched_paths = [p for p in self.multimedia_map.keys() if p in paths]
            if len(paths) > 0:
                totals.append({
                    'media_type': mm.get_nice_name(),
                    'totals': len(paths),
                    'matched': len(matched_paths),
                    'icon_class': mm.get_icon_class(),
                    'paths': matched_paths,
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

    def check_media_state(self):
        has_missing_refs = False

        for media in self.all_media:
            try:
                self.multimedia_map[media.path]
            except KeyError:
                has_missing_refs = True

        return {
            "has_media": bool(self.all_media),
            "has_form_errors": self.media_form_errors,
            "has_missing_refs": has_missing_refs,
        }

    def archive_logos(self):
        """
        Archives any uploaded logos in the application.
        """
        has_archived = False
        if LOGO_ARCHIVE_KEY not in self.archived_media:
            self.archived_media[LOGO_ARCHIVE_KEY] = {}
        for slug, logo_data in self.logo_refs.items():
            self.archived_media[LOGO_ARCHIVE_KEY][slug] = logo_data
            has_archived = True
            del self.logo_refs[slug]
        return has_archived

    def restore_logos(self):
        """
        Restores any uploaded logos in the application.
        """
        has_restored = False
        if hasattr(self, 'archived_media') and LOGO_ARCHIVE_KEY in self.archived_media:
            for slug, logo_data in self.archived_media[LOGO_ARCHIVE_KEY].items():
                self.logo_refs[slug] = logo_data
                has_restored = True
                del self.archived_media[LOGO_ARCHIVE_KEY][slug]
        return has_restored


