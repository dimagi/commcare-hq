from django import forms
from django.forms.util import ErrorList
from corehq.apps.hqmedia import utils
from corehq.apps.hqmedia.models import CommCareMultimedia, CommCareImage, CommCareAudio
import zipfile

class HQMediaZipUploadForm(forms.Form):

    zip_file = forms.FileField(required=True)
    repopulate_multimedia_map = forms.BooleanField(required=False,
                                label="Remove all previous references to multimedia files in my application.")
    replace_existing_media = forms.BooleanField(required=False,
                                label="Replace any existing multimedia files with this file.")

    def clean_zip_file(self):
        if 'zip_file' in self.cleaned_data:
            zip_file = self.cleaned_data['zip_file']
            if zip_file.content_type != 'application/zip':
                raise forms.ValidationError('Only .ZIP archive files are allowed.')
            else:
                # Verify that it's a valid zipfile
                zip = zipfile.ZipFile(zip_file)
                bad_file = zip.testzip()
                if bad_file:
                    msg = '"%s" in the .ZIP archive is corrupt.' % (bad_file,)
                    raise forms.ValidationError(msg)
                return zip

    def save(self, domain, app, username, cache_handler=None):
        orig_images, orig_audio = utils.get_multimedia_filenames(app)
        form_images = [i.replace(utils.MULTIMEDIA_PREFIX, '').lower().strip() for i in orig_images]
        form_audio = [a.replace(utils.MULTIMEDIA_PREFIX, '').lower().strip() for a in orig_audio]

        if self.cleaned_data["repopulate_multimedia_map"]:
            app.multimedia_map = {}
            app.save()
        replace_attachment = self.cleaned_data["replace_existing_media"]

        zip = self.cleaned_data["zip_file"]
        num_files = len(zip.namelist())
        if cache_handler:
            cache_handler.sync()
            cache_handler.data["processed_length"] = num_files
            cache_handler.save()
        
        unknown_files = []
        for index, path in enumerate(zip.namelist()):
            path = path.strip()
            path_lower = path.lower()
            if path_lower.endswith("/") or path_lower.endswith("\\") or \
                path_lower.endswith(".ds_store"):
                continue

            media = None
            form_path = None
            data = None
            if path_lower in form_images:
                form_path = orig_images[form_images.index(path_lower)]
                data = zip.read(path)
                media = CommCareImage.get_by_data(data)
            elif path_lower in form_audio:
                form_path = orig_audio[form_audio.index(path_lower)]
                data = zip.read(path)
                media = CommCareAudio.get_by_data(data)
            else:
                unknown_files.append(path)

            if media:
                media.attach_data(data,
                     upload_path=path,
                     username=username,
                     replace_attachment=replace_attachment)
                media.add_domain(domain)
                app.create_mapping(media, form_path)
            if cache_handler:
                cache_handler.sync()
                cache_handler.data["processed"] = index+1
                cache_handler.save()
        zip.close()
        return unknown_files

class HQMediaFileUploadForm(forms.Form):

    media_file = forms.FileField(required=True)
    multimedia_form_path = forms.CharField(required=True, widget=forms.HiddenInput)
    multimedia_class = forms.CharField(initial="CommCareMultimedia", widget=forms.HiddenInput)
    multimedia_upload_action = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def clean_media_file(self):
        if 'media_file' in self.cleaned_data:
            media_file = self.cleaned_data['media_file']
            if media_file.content_type == 'application/zip':
                raise forms.ValidationError('Please use the zip file uploader to upload zip files.')
            return media_file

    def save(self, domain, app, username):
        pass