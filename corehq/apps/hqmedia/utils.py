from django.core.urlresolvers import reverse
from django.utils.datastructures import SortedDict
import os
import sys
import logging
from corehq.apps.app_manager.xform import XFormValidationError, XFormError
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from corehq.apps.hqmedia.models import CommCareMultimedia, CommCareAudio, CommCareImage, HQMediaMapItem

MULTIMEDIA_PREFIX = "jr://file/"
IMAGE_MIMETYPES = ["image/jpeg", "image/gif", "image/png"]
AUDIO_MIMETYPES = ["audio/mpeg", "audio/mpeg3"]
ZIP_MIMETYPES = ["application/zip"]

def get_sorted_multimedia_refs(app):
    images = {}
    audio_files = {}
    has_error = False

    for m in app.get_modules():
        for f in m.get_forms():
            try:
                parsed = f.wrapped_xform()
                if not parsed.exists():
                    continue
                f.validate_form()
                for i in parsed.image_references:
                    if i not in images:
                        images[i] = []
                    images[i].append((m,f))
                for i in parsed.audio_references:
                    if i not in audio_files:
                        audio_files[i] = []
                    audio_files[i].append((m,f))
            except (XFormValidationError, XFormError):
                has_error = True
    sorted_images = SortedDict()
    sorted_audio = SortedDict()
    for k in sorted(images):
        if k:
            sorted_images[k] = images[k]
    for k in sorted(audio_files):
        if k:
            sorted_audio[k] = audio_files[k]
    return sorted_images, sorted_audio, has_error

def get_multimedia_filenames(app):
    images = []
    audio_files = []
    has_error = False
    for m in app.get_modules():
        for f in m.get_forms():
            try:
                parsed = f.wrapped_xform()
                if not parsed.exists():
                    continue
                f.validate_form()
                for i in parsed.image_references:
                    if i and i not in images:
                        images.append(i)
                for a in parsed.audio_references:
                    if a and a not in audio_files:
                        audio_files.append(a)
            except (XFormValidationError, XFormError):
                has_error = True
    return images, audio_files, has_error

class HQMediaMatcher():
    image_paths = {}
    audio_paths = {}
    images = []
    audio = []
    specific_params = {}

    def __init__(self, app, domain, username, specific_params, match_filename=False):
        if specific_params:
            self.specific_params = specific_params
        self.match_filename = match_filename
        if not self.specific_params:
            self.image_paths, self.audio_paths, _ = get_multimedia_filenames(app)
            if self.match_filename:
                self.images = [os.path.basename(i.replace(MULTIMEDIA_PREFIX, '').lower().strip())
                               for i in self.image_paths]
                self.audio = [os.path.basename(a.replace(MULTIMEDIA_PREFIX, '').lower().strip())
                              for a in self.audio_paths]
            else:
                self.images = [i.replace(MULTIMEDIA_PREFIX, '').lower().strip() for i in self.image_paths]
                self.audio = [a.replace(MULTIMEDIA_PREFIX, '').lower().strip() for a in self.audio_paths]

        self.app = app
        self.domain = domain
        self.username = username

    def clear_map(self):
        self.app.multimedia_map = {}
        self.app.save()

    def owner(self):
        project = Domain.get_by_name(self.domain)
        if project.organization:
            return project.organization_doc()
        else:
            return CouchUser.get_by_username(self.username)

    def match_zipped(self, zip, replace_existing_media=True, **kwargs):
        unknown_files = []
        matched_audio = []
        matched_images = []
        errors = []
        try:
            for index, path in enumerate(zip.namelist()):
                path = path.strip()
                filename = path.lower()
                basename = os.path.basename(path.lower())
                is_image = False

                if not basename:
                    continue

                if self.match_filename:
                    filename = basename

                media = None
                form_path = None
                data = None

                if filename in self.images:
                    form_path = self.image_paths[self.images.index(filename)]
                    data = zip.read(path)
                    media = CommCareImage.get_by_data(data)
                    is_image = True
                elif filename in self.audio:
                    form_path = self.audio_paths[self.audio.index(filename)]
                    data = zip.read(path)
                    media = CommCareAudio.get_by_data(data)
                else:
                    unknown_files.append(path)

                if media:
                    try:
                        media.attach_data(data,
                            upload_path=path,
                            username=self.username,
                            replace_attachment=replace_existing_media)
                        media.add_domain(self.domain, owner=True)
                        media.update_or_add_license(self.domain,
                                                    type=kwargs.get('license', ''),
                                                    author=kwargs.get('author', ''))
                        self.app.create_mapping(media, form_path)
                        match_map = HQMediaMapItem.format_match_map(form_path, media.doc_type, media._id, path)
                        if is_image:
                            matched_images.append(match_map)
                        else:
                            matched_audio.append(match_map)
                    except Exception as e:
                        errors.append("%s (%s)" % (e, filename))
            zip.close()
        except Exception as e:
            logging.error(e)
            errors.append(e.message)

        return matched_images, matched_audio, unknown_files, errors

    def match_file(self, uploaded_file, replace_existing_media=True, **kwargs):
        errors = []
        try:
            if self.specific_params and self.specific_params['media_type'][0].startswith('CommCare'):
                media_class = getattr(sys.modules[__name__], self.specific_params['media_type'][0])
                form_path = self.specific_params['path'][0]
                replace_existing_media = self.specific_params['replace_attachment'][0]

                filename = uploaded_file.name
                data = uploaded_file.file.read()
                media = media_class.get_by_data(data)
            else:
                filename = uploaded_file.name

                if filename in self.images:
                    form_path = self.image_paths[self.images.index(filename)]
                    data = uploaded_file.file.read()
                    media = CommCareImage.get_by_data(data)
                elif filename in self.audio:
                    form_path = self.audio_paths[self.audio.index(filename)]
                    data = uploaded_file.file.read()
                    media = CommCareAudio.get_by_data(data)
                else:
                    uploaded_file.close()
                    return False, {}, errors
            if media:
                media.attach_data(data,
                    upload_path=filename,
                    username=self.username,
                    replace_attachment=replace_existing_media)
                media.add_domain(self.domain, owner=True, **kwargs)
                media.update_or_add_license(self.domain, type=kwargs.get('license', ''), author=kwargs.get('author', ''))
                self.app.create_mapping(media, form_path)

                return True, HQMediaMapItem.format_match_map(form_path, media.doc_type, media._id, filename), errors
        except Exception as e:
            logging.error(e)
            errors.append(e.message)

        return False, {}, errors





