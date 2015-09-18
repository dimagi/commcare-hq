from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.generator import SectionSuiteContributor
from corehq.apps.app_manager.suite_xml.xml_models import LocaleResource, XFormResource
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.util import languages_mapping


class FormResourceContributor(SectionSuiteContributor):
    section = 'xform_resources'

    def get_section_contributions(self):
        first = []
        last = []
        for form_stuff in self.app.get_forms(bare=False):
            form = form_stuff["form"]
            if form_stuff['type'] == 'module_form':
                path = './modules-{module.id}/forms-{form.id}.xml'.format(**form_stuff)
                this_list = first
            else:
                path = './user_registration.xml'
                this_list = last
            resource = XFormResource(
                id=id_strings.xform_resource(form),
                version=form.get_version(),
                local=path,
                remote=path,
            )
            if form_stuff['type'] == 'module_form' and self.app.build_version >= '2.9':
                resource.descriptor = u"Form: (Module {module_name}) - {form_name}".format(
                    module_name=trans(form_stuff["module"]["name"], langs=[self.app.default_language]),
                    form_name=trans(form["name"], langs=[self.app.default_language])
                )
            elif path == './user_registration.xml':
                resource.descriptor=u"User Registration Form"
            this_list.append(resource)
        for x in first:
            yield x
        for x in last:
            yield x


class LocaleResourceContributor(SectionSuiteContributor):
    section = 'locale_resources'

    def get_section_contributions(self):
        for lang in ["default"] + self.app.build_langs:
            path = './{lang}/app_strings.txt'.format(lang=lang)
            resource = LocaleResource(
                language=lang,
                id=id_strings.locale_resource(lang),
                version=self.app.version,
                local=path,
                remote=path,
            )
            if self.app.build_version >= '2.9':
                unknown_lang_txt = u"Unknown Language (%s)" % lang
                resource.descriptor = u"Translations: %s" % languages_mapping().get(lang, [unknown_lang_txt])[0]
            yield resource
