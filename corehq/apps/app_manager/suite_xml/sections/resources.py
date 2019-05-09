from __future__ import absolute_import
from __future__ import unicode_literals

from distutils.version import LooseVersion

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.xml_models import LocaleResource, XFormResource, \
    PracticeUserRestoreResource, ReleaseInfoXFormResource
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import languages_mapping


class FormResourceContributor(SectionContributor):
    section_name = 'xform_resources'

    def get_section_elements(self):
        from corehq.apps.app_manager.models import ShadowForm
        for form_stuff in self.app.get_forms(bare=False):
            form = form_stuff["form"]
            if isinstance(form, ShadowForm):
                continue
            path = './modules-{module.id}/forms-{form.id}.xml'.format(**form_stuff)
            if self.build_profile_id:
                remote_path = '{path}?profile={profile}'.format(path=path, profile=self.build_profile_id)
            else:
                remote_path = path

            if form.is_release_notes_form:
                if form.enable_release_notes:
                    element_class = ReleaseInfoXFormResource
                else:
                    continue
            else:
                element_class = XFormResource
            resource = element_class(
                id=id_strings.xform_resource(form),
                version=form.get_version(),
                local=path,
                remote=remote_path,
            )
            if self.app.build_version and self.app.build_version >= LooseVersion('2.9'):
                default_lang = self.app.default_language if not self.build_profile_id \
                    else self.app.build_profiles[self.build_profile_id].langs[0]
                resource.descriptor = "Form: (Module {module_name}) - {form_name}".format(
                    module_name=trans(form_stuff["module"]["name"], langs=[default_lang]),
                    form_name=trans(form["name"], langs=[default_lang])
                )
            yield resource


class LocaleResourceContributor(SectionContributor):
    section_name = 'locale_resources'

    def get_section_elements(self):
        langs = self.app.get_build_langs(self.build_profile_id)
        for lang in ["default"] + langs:
            path = './{lang}/app_strings.txt'.format(lang=lang)
            if self.build_profile_id:
                remote_path = '{path}?profile={profile}'.format(path=path, profile=self.build_profile_id)
            else:
                remote_path = path
            resource = LocaleResource(
                language=lang,
                id=id_strings.locale_resource(lang),
                version=self.app.version,
                local=path,
                remote=remote_path,
            )
            if self.app.build_version and self.app.build_version >= LooseVersion('2.9'):
                unknown_lang_txt = "Unknown Language (%s)" % lang
                resource.descriptor = "Translations: %s" % languages_mapping().get(lang, [unknown_lang_txt])[0]
            yield resource


class PracticeUserRestoreContributor(SectionContributor):
    section_name = 'practice_user_restore_resources'

    def get_section_elements(self):
        user = self.app.get_practice_user(self.build_profile_id)
        path = "./practice_user_restore.xml"
        if self.build_profile_id:
            remote_path = '{path}?profile={profile}'.format(path=path, profile=self.build_profile_id)
        else:
            remote_path = path
        yield PracticeUserRestoreResource(
            id="practice-user-restore",
            version=user.demo_restore_id,
            local=path,
            remote=remote_path,
            descriptor="practice user restore"
        )
