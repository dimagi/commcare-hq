from django import forms
import os
from corehq.apps.hqmedia import utils
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio
import zipfile

class NewXFormForm(forms.Form):
    """Potentially confusing name; HTML Form for creating/uploading a new xform"""
    name = forms.CharField(max_length=50)
    
class NewAppForm(forms.Form):
    name = forms.CharField(max_length=50)

class NewModuleForm(forms.Form):
    name = forms.CharField(max_length=50)

class ModuleConfigForm(forms.Form):
    pass

class ZipUploadForm(forms.Form):

    zip_file = forms.FileField()

    def clean_zip_file(self):
        print "clean zip file"
        if 'zip_file' in self.cleaned_data:
            zip_file = self.cleaned_data['zip_file']
            if zip_file.content_type != 'application/zip':
                msg = 'Only .ZIP archive files are allowed.'
                raise forms.ValidationError(msg)
            else:
                # Verify that it's a valid zipfile
                zip = zipfile.ZipFile(zip_file)
                bad_file = zip.testzip()
                if bad_file:
                    msg = '"%s" in the .ZIP archive is corrupt.' % (bad_file,)
                    raise forms.ValidationError(msg)
                return zip

    def save(self, domain, app, username):
        orig_images, orig_audio = utils.get_multimedia_filenames(app)
        form_images = [i.replace(utils.MULTIMEDIA_PREFIX, '').lower() for i in orig_images]
        form_audio = [a.replace(utils.MULTIMEDIA_PREFIX, '').lower() for a in orig_audio]
        zip = self.cleaned_data["zip_file"]
        for path in zip.namelist():
            path_lower = path.lower()

            media = None
            form_path = None
            filename = None
            data = None
            if path_lower in form_images:
                form_path = orig_images[form_images.index(path_lower)]
                filename = os.path.basename(form_path)
                data = zip.read(path)
                media = CommCareImage.get_by_data(data)
            elif path_lower in form_audio:
                form_path = orig_audio[form_audio.index(path_lower)]
                filename = os.path.basename(form_path)
                data = zip.read(path)
                media = CommCareAudio.get_by_data(data)
            if media:
                media.attach_data(data,
                     filename,
                     upload_path=path,
                     username=username)
                media.add_domain(domain)
                app.create_mapping(media, filename, form_path)

        zip.close()