from dimagi.ext.couchdbkit import (
    IntegerProperty,
    SchemaProperty,
    StringProperty,
)
from dimagi.utils.couch.undo import DeleteRecord
from django.utils.translation import gettext as _

from corehq.apps.app_manager.templatetags.xforms_extras import (
    clean_trans,
)
from corehq.apps.cleanup.models import DeletedCouchDoc


class DeleteApplicationRecord(DeleteRecord):

    app_id = StringProperty()

    def undo(self):
        from .applications import ApplicationBase
        app = ApplicationBase.get(self.app_id)
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        app.doc_type = app.get_doc_type()
        app.save(increment_version=False)


class DeleteModuleRecord(DeleteRecord):
    from .modules import ModuleBase

    app_id = StringProperty()
    module_id = IntegerProperty()
    module = SchemaProperty(ModuleBase)

    def undo(self):
        from .applications import Application
        app = Application.get(self.app_id)
        modules = app.modules
        modules.insert(self.module_id, self.module)
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        app.modules = modules
        app.save()


class DeleteFormRecord(DeleteRecord):
    from .forms import FormBase

    app_id = StringProperty()
    module_id = IntegerProperty()
    module_unique_id = StringProperty()
    form_id = IntegerProperty()
    form = SchemaProperty(FormBase)

    def undo(self):
        from .applications import Application
        app = Application.get(self.app_id)
        if self.module_unique_id is not None:
            name = clean_trans(self.form.name, app.default_language)
            module = app.get_module_by_unique_id(
                self.module_unique_id,
                error=_("Could not find form '{}'").format(name)
            )
        else:
            module = app.modules[self.module_id]
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        forms = module.forms
        forms.insert(self.form_id, self.form)
        module.forms = forms
        app.save()
