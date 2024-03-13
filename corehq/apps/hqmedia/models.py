import hashlib
import mimetypes
from copy import copy
from datetime import datetime
from io import BytesIO

from django.db import models
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.translation import gettext as _

import magic
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from lxml import etree
from memoized import memoized
from PIL import Image

from dimagi.ext.couchdbkit import (
    DateTimeProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    SafeSaveDocument,
    SchemaDictProperty,
    SchemaListProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.couch.database import get_safe_read_kwargs, iter_docs
from dimagi.utils.couch.resource_conflict import retry_resource

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.exceptions import XFormException
from corehq.apps.app_manager.templatetags.xforms_extras import clean_trans
from corehq.apps.app_manager.xform import XFormValidationError
from corehq.apps.domain import SHARED_DOMAIN
from corehq.apps.domain.models import LICENSE_LINKS, LICENSES
from corehq.apps.hqmedia.exceptions import BadMediaFileException
from corehq.blobs.mixin import CODES, BlobMixin
from corehq.util.view_utils import absolute_reverse

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
    _blobdb_type_code = CODES.multimedia

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
            license = HQMediaLicense(domain=domain, type=type, author=author,
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
                # put_attchment blows away existing data, so make sure an id has been assigned
                # to this guy before we do it. This is the usual path; remote apps are the exception.
                self.save()
            self.put_attachment(
                data,
                attachment_id,
                content_type=self.get_mime_type(data, filename=original_filename),
                domain=SHARED_DOMAIN,
            )
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
            # (which should be impossible) it will transfer ownership to all copiers... not necessarily a bad
            # thing, just something to be aware of
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

    def get_file_extension(self):
        extension = ''
        if self.aux_media:
            extension = '.{}'.format(self.aux_media[-1]['uploaded_filename'].split(".")[-1])
        return extension

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
    def get_doc_types(cls):
        return ('CommCareImage', 'CommCareAudio', 'CommCareVideo')

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
            migrated = [HQMediaLicense(domain=domain, type=type)._doc
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
                return "{} x {} px".format(width, height)

    @classmethod
    def get_image_object(cls, data):
        try:
            return Image.open(BytesIO(data))
        except IOError:
            raise BadMediaFileException(_('Upload is not a valid image file.'))

    @classmethod
    def _get_resized_image(cls, image, size):
        if image.mode not in ["RGB", "RGBA"]:
            image = image.convert("RGB")
        o = BytesIO()
        try:
            image.thumbnail(size, Image.Resampling.LANCZOS)
        except IndexError:
            raise ImageThumbnailError()
        image.save(o, format="PNG")
        return o.getvalue()

    @classmethod
    def get_invalid_image_data(cls):
        import os
        invalid_image_path = os.path.join(os.path.dirname(__file__), 'static/hqmedia/images/invalid_image.png')
        return Image.open(open(invalid_image_path, 'rb'))

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
        return "fa-regular fa-image"


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
    version = IntegerProperty()
    unique_id = StringProperty()
    upstream_media_id = StringProperty()

    @property
    def url(self):
        return reverse("hqmedia_download", args=[self.media_type, self.multimedia_id]) \
            if self.multimedia_id else ""

    @classmethod
    def gen_unique_id(cls, m_id, path):
        return hashlib.md5(b"%s: %s" % (path.encode('utf-8'), m_id.encode('utf-8'))).hexdigest()


class ApplicationMediaReference(object):
    """
        Generated when all_media is queried and stored in memory.

        Contains all the information needed to know where / how this the media PATH is stored in the application.
        Provides no link to a multimedia object---link comes from the application's multimedia map.
        Useful info for user-facing things.
    """

    def __init__(self, path, module_unique_id=None, module_name=None,
                 form_unique_id=None, form_name=None, form_order=None, media_class=None,
                 is_menu_media=False, app_lang=None, use_default_media=False):

        if not isinstance(path, str):
            path = ''
        self.path = path.strip()

        if not issubclass(media_class, CommCareMultimedia):
            raise ValueError("media_class should be a type of CommCareMultimedia")

        self.module_unique_id = module_unique_id
        self.module_name = module_name

        self.form_unique_id = form_unique_id
        self.form_name = form_name
        self.form_order = form_order

        self.media_class = media_class
        self.is_menu_media = is_menu_media

        self.app_lang = app_lang or "en"

        self.use_default_media = use_default_media

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

    def as_dict(self):
        return {
            'module': {
                'name': self.get_module_name(),
                'unique_id': self.module_unique_id,
            },
            'form': {
                'name': self.get_form_name(),
                'unique_id': self.form_unique_id,
                'order': self.form_order,
            },
            'is_menu_media': self.is_menu_media,
            'media_class': self.media_class.__name__,
            'path': self.path,
            "icon_class": self.media_class.get_icon_class(),
            "media_type": self.media_class.get_nice_name(),
            "use_default_media": self.use_default_media,
        }

    def _get_name(self, raw_name):
        if not raw_name:
            return ""
        if not isinstance(raw_name, dict):
            return raw_name
        return raw_name.get(self.app_lang, list(raw_name.values())[0])

    def get_module_name(self):
        return self._get_name(self.module_name)

    def get_form_name(self):
        return self._get_name(self.form_name)


class MediaMixin(object):
    """
        An object that has multimedia associated with it.
        Used by apps, modules, forms.
    """
    def get_media_ref_kwargs(self):
        raise NotImplementedError

    def all_media(self, lang=None):
        """
            Finds all the multimedia IMAGES and AUDIO referenced in this object
            Returns list of ApplicationMediaReference objects
        """
        raise NotImplementedError

    def get_references(self, lang=None):
        """
            Used for the multimedia controller.
        """
        return [m.as_dict() for m in self.all_media(lang=lang)]

    def get_relevant_multimedia_map(self, app):
        references = self.get_references()
        return {r['path']: app.multimedia_map[r['path']]
                for r in references if r['path'] in app.multimedia_map}

    def rename_media(self, old_path, new_path):
        """
            Returns a count of number of changes made.
            Should rename each item returned by all_media.
        """
        raise NotImplementedError

    @memoized
    def all_media_paths(self, lang=None):
        return set([m.path for m in self.all_media(lang=lang)])

    @memoized
    def get_all_paths_of_type(self, media_type):
        return set([m.path for m in self.all_media() if m.media_class.__name__ == media_type])

    def menu_media(self, menu, lang=None):
        """
            Convenience method. Gets the ApplicationMediaReference for a menu that's
            associated with this MediaMixin (which may be self or a different attribute)

            Note that "menu" may refer to any object that implements NavMenuItemMediaMixin,
            like a module or a form.
        """
        kwargs = self.get_media_ref_kwargs()
        media = []
        media.extend([ApplicationMediaReference(image, media_class=CommCareImage, is_menu_media=True, **kwargs)
                      for image in menu.all_image_paths(lang=lang) if image])
        media.extend([ApplicationMediaReference(audio, media_class=CommCareAudio, is_menu_media=True, **kwargs)
                      for audio in menu.all_audio_paths(lang=lang) if audio])
        return media

    def rename_menu_media(self, menu, old_path, new_path):
        """
            Convenience method, similar to menu_media.
        """
        app = self.get_app()
        update_count = 0
        for lang in app.langs:
            if menu.icon_by_language(lang) == old_path:
                menu.set_icon(lang, new_path)
                update_count += 1
            if menu.audio_by_language(lang) == old_path:
                menu.set_audio(lang, new_path)
                update_count += 1
        return update_count


class ModuleMediaMixin(MediaMixin):
    def get_media_ref_kwargs(self):
        return {
            'app_lang': self.get_app().default_language,
            'module_name': self.name,
            'module_unique_id': self.unique_id,
            'form_name': None,
            'form_unique_id': None,
            'form_order': None,
        }

    def all_media(self, lang=None):
        kwargs = self.get_media_ref_kwargs()
        media = []

        media.extend(self.menu_media(self, lang=lang))

        # Registration from case list
        if self.case_list_form.form_id:
            media.extend(self.menu_media(self.case_list_form, lang=lang))

        # Case list menu item
        if hasattr(self, 'case_list') and self.case_list.show:
            media.extend(self.menu_media(self.case_list, lang=lang))

        # Case search and claim menu items
        if hasattr(self, 'search_config'):
            media.extend(self.menu_media(self.search_config.search_label, lang=lang))
            media.extend(self.menu_media(self.search_config.search_again_label, lang=lang))

        for name, details, display in self.get_details():
            # Case list lookup - not language-specific
            if display and details.display == 'short' and details.lookup_enabled and details.lookup_image:
                media.append(ApplicationMediaReference(details.lookup_image, media_class=CommCareImage,
                                                       is_menu_media=True, **kwargs))

            # Print template - not language-specific
            if display and details.display == 'long' and details.print_template:
                media.append(ApplicationMediaReference(details.print_template['path'],
                                                       media_class=CommCareMultimedia, **kwargs))

            # Icon-formatted columns
            for column in details.get_columns():
                if column.format == 'enum-image' or column.format == 'clickable-icon':
                    for map_item in column.enum:
                        icon = clean_trans(map_item.value, [lang] + self.get_app().langs)
                        if icon:
                            media.append(ApplicationMediaReference(icon, media_class=CommCareImage,
                                                                   is_menu_media=True, **kwargs))

        return media

    def rename_media(self, old_path, new_path):
        count = 0

        count += self.rename_menu_media(self, old_path, new_path)

        # Registration from case list
        if self.case_list_form.form_id:
            count += self.rename_menu_media(self.case_list_form, old_path, new_path)

        # Case list menu item
        if hasattr(self, 'case_list') and self.case_list.show:
            count += self.rename_menu_media(self.case_list, old_path, new_path)

        # Case search and claim menu items
        if hasattr(self, 'search_config'):
            count += self.rename_menu_media(self.search_config.search_label, old_path, new_path)
            count += self.rename_menu_media(self.search_config.search_again_label, old_path, new_path)

        for name, details, display in self.get_details():
            # Case list lookup
            if display and details.display == 'short' and details.lookup_enabled and details.lookup_image:
                if details.lookup_image == old_path:
                    details.lookup_image = new_path
                    count += 1

            # Print template
            if display and details.display == 'long' and details.print_template:
                details.print_template['path'] = new_path
                count += 1

            # Icon-formatted columns
            for column in details.get_columns():
                if column.format == 'enum-image':
                    for map_item in column.enum:
                        for lang, icon in map_item.value.items():
                            if icon == old_path:
                                map_item.value[lang] = new_path
                                count += 1

        return count


class FormMediaMixin(MediaMixin):
    def get_media_ref_kwargs(self):
        module = self.get_module()
        return {
            'app_lang': module.get_app().default_language,
            'module_name': module.name,
            'module_unique_id': module.unique_id,
            'form_name': self.name,
            'form_unique_id': self.unique_id,
            'form_order': self.id,
        }

    @memoized
    def memoized_xform(self):
        return self.wrapped_xform()

    def all_media(self, lang=None):
        kwargs = self.get_media_ref_kwargs()

        media = copy(self.menu_media(self, lang=lang))

        # Form questions
        try:
            parsed = self.wrapped_xform()
            if parsed.exists():
                self.validate_form()
            else:
                return media
        except (XFormValidationError, XFormException):
            return media

        for image in parsed.image_references(lang=lang):
            if image:
                media.append(ApplicationMediaReference(image, media_class=CommCareImage, **kwargs))
        for audio in parsed.audio_references(lang=lang):
            if audio:
                media.append(ApplicationMediaReference(audio, media_class=CommCareAudio, **kwargs))
        for video in parsed.video_references(lang=lang):
            if video:
                media.append(ApplicationMediaReference(video, media_class=CommCareVideo, **kwargs))
        for text in parsed.text_references(lang=lang):
            if text:
                media.append(ApplicationMediaReference(text, media_class=CommCareMultimedia, **kwargs))

        return media

    def rename_media(self, old_path, new_path):
        menu_count = self.rename_menu_media(self, old_path, new_path)

        xform_count = 0
        if self.form_type != 'shadow_form':
            xform_count = self.memoized_xform().rename_media(old_path, new_path)
            if xform_count:
                self.source = etree.tostring(self.memoized_xform().xml, encoding='utf-8').decode('utf-8')

        return menu_count + xform_count


class ApplicationMediaMixin(Document, MediaMixin):
    """
        Manages multimedia for itself and sub-objects.
    """

    # keys are the paths to each file in the final application media zip
    multimedia_map = SchemaDictProperty(HQMediaMapItem)

    # paths to custom logos
    logo_refs = DictProperty()

    # where we store references to the old logos (or other multimedia) on a downgrade,
    # so that information is not lost
    archived_media = DictProperty()

    @memoized
    def all_media(self, lang=None):
        """
            Somewhat counterituitively, this contains all media in the app EXCEPT app-level media (logos).
        """
        media = []
        self.media_form_errors = False

        for module in [m for m in self.get_modules() if m.uses_media()]:
            media.extend(module.all_media(lang=lang))
            for form in module.get_forms():
                try:
                    form.validate_form()
                except (XFormValidationError, XFormException):
                    self.media_form_errors = True
                else:
                    media.extend(form.all_media(lang=lang))
        return media

    def multimedia_map_for_build(self, build_profile=None, remove_unused=False):
        if self.multimedia_map is None:
            self.multimedia_map = {}

        if self.multimedia_map and remove_unused:
            self.remove_unused_mappings()

        if not build_profile or not domain_has_privilege(self.domain, privileges.BUILD_PROFILES):
            return self.multimedia_map

        requested_media = copy(self.logo_paths)   # logos aren't language-specific
        for lang in build_profile.langs:
            requested_media |= self.all_media_paths(lang=lang)

        return {path: self.multimedia_map[path] for path in requested_media if path in self.multimedia_map}

    # The following functions (get_menu_media, get_case_list_form_media, get_case_list_menu_item_media,
    # get_case_list_lookup_image, _get_item_media, and get_media_ref_kwargs) are used to set up context
    # for app manager settings pages. Ideally, they'd be moved into ModuleMediaMixin and FormMediaMixin
    # and perhaps share logic with those mixins' versions of all_media.
    def get_menu_media(self, module, form=None, form_index=None, to_language=None):
        if not module:
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(module, form=form, form_index=form_index, is_menu_media=True)
        media_kwargs.update(to_language=to_language or self.default_language)
        item = form or module
        return self._get_item_media(item, media_kwargs)

    def get_case_list_form_media(self, module, to_language=None):
        if not module:
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(module)
        media_kwargs.update(to_language=to_language or self.default_language)
        return self._get_item_media(module.case_list_form, media_kwargs)

    def get_case_list_menu_item_media(self, module, to_language=None):
        if not module or not module.uses_media() or not hasattr(module, 'case_list'):
            # user_registration isn't a real module, for instance
            return {}
        media_kwargs = self.get_media_ref_kwargs(module)
        media_kwargs.update(to_language=to_language or self.default_language)
        return self._get_item_media(module.case_list, media_kwargs)

    def get_case_search_label_media(self, module, label, to_language=None):
        media_kwargs = self.get_media_ref_kwargs(module)
        media_kwargs.update(to_language=to_language or self.default_language)
        return self._get_item_media(label, media_kwargs)

    def get_case_list_lookup_image(self, module, type='case'):
        if not module:
            return {}
        media_kwargs = self.get_media_ref_kwargs(module)
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
            use_default_media=item.use_default_image_for_all,
            **media_kwargs
        )
        image_ref = image_ref.as_dict()
        menu_media['image'] = image_ref

        audio_ref = ApplicationMediaReference(
            item.audio_by_language(to_language),
            media_class=CommCareAudio,
            use_default_media=item.use_default_audio_for_all,
            **media_kwargs
        )
        audio_ref = audio_ref.as_dict()
        menu_media['audio'] = audio_ref
        return menu_media

    def get_media_ref_kwargs(self, module, form=None, form_index=None, is_menu_media=False):
        return {
            'app_lang': self.default_language,
            'module_name': module.name,
            'module_unique_id': module.unique_id,
            'form_name': form.name if form else None,
            'form_unique_id': form.unique_id if form else None,
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
        if self.check_media_state()['has_form_errors']:
            return
        paths = list(self.multimedia_map) if self.multimedia_map else []
        permitted_paths = self.all_media_paths() | self.logo_paths
        for path in paths:
            if path not in permitted_paths:
                map_changed = True
                del self.multimedia_map[path]

        if map_changed:
            self.save()

    def create_mapping(self, multimedia, path, save=True):
        """
            This creates the mapping of a path to the multimedia in an application
            to the media object stored in couch.
        """
        path = path.strip()
        map_item = HQMediaMapItem()
        map_item.multimedia_id = multimedia._id
        map_item.unique_id = HQMediaMapItem.gen_unique_id(map_item.multimedia_id, path)
        map_item.media_type = multimedia.doc_type
        self.multimedia_map[path] = map_item

        if save:
            try:
                self.save()
            except ResourceConflict:
                # Attempt to fetch the document again.
                updated_doc = self.get(self._id)
                updated_doc.create_mapping(multimedia, path)

    def get_media_objects(self, build_profile_id=None, remove_unused=False, multimedia_map=None):
        """
            Gets all the media objects stored in the multimedia map.
            If passed a profile, will only get those that are used
            in a language in the profile.

            Returns a generator of tuples, where the first item in the tuple is
            the path (jr://...) and the second is the object (CommCareMultimedia or a subclass)
        """
        # preload all the docs to avoid excessive couch queries.
        # these will all be needed in memory anyway so this is ok.
        build_profile = self.build_profiles[build_profile_id] if build_profile_id else None
        if not multimedia_map:
            multimedia_map = self.multimedia_map_for_build(build_profile=build_profile,
                                                           remove_unused=remove_unused)
        expected_ids = [map_item.multimedia_id for map_item in multimedia_map.values()]
        raw_docs = dict((d["_id"], d) for d in iter_docs(CommCareMultimedia.get_db(), expected_ids))
        for path, map_item in multimedia_map.items():
            media_item = raw_docs.get(map_item.multimedia_id)
            if media_item:
                media_cls = CommCareMultimedia.get_doc_class(map_item.media_type)
                yield path, media_cls.wrap(media_item)
            else:
                # Re-attempt to fetch media directly from couch
                media = CommCareMultimedia.get_doc_class(map_item.media_type)
                try:
                    media = media.get(map_item.multimedia_id)
                    yield path, media
                except ResourceNotFound as e:
                    if toggles.CAUTIOUS_MULTIMEDIA.enabled(self.domain):
                        raise e

    def get_object_map(self, multimedia_map=None):
        object_map = {}
        for path, media_obj in self.get_media_objects(remove_unused=False, multimedia_map=multimedia_map):
            object_map[path] = media_obj.get_media_info(path)
        return object_map

    def get_reference_totals(self):
        """
            Returns a list of totals of each type of media in the application and total matches.
        """
        totals = []
        for mm in [CommCareMultimedia.get_doc_class(t) for t in CommCareMultimedia.get_doc_types()]:
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

    def check_media_state(self):
        has_missing_refs = False

        for media in self.all_media():
            try:
                self.multimedia_map[media.path]
            except KeyError:
                has_missing_refs = True

        return {
            "has_media": bool(self.all_media()),
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
        for slug, logo_data in list(self.logo_refs.items()):
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
            for slug, logo_data in list(self.archived_media[LOGO_ARCHIVE_KEY].items()):
                self.logo_refs[slug] = logo_data
                has_restored = True
                del self.archived_media[LOGO_ARCHIVE_KEY][slug]
        return has_restored


class LogoForSystemEmailsReference(models.Model):
    domain = models.CharField(max_length=255, unique=True, null=False)
    # Doc ID of the CommCareImage the object references
    image_id = models.CharField(max_length=255, null=False)

    def full_url_to_image(self):
        from corehq.apps.hqmedia.views import ViewMultimediaFile
        image = CommCareImage.get(self.image_id)
        return absolute_reverse(ViewMultimediaFile.urlname, args=[image.doc_type, image._id])
