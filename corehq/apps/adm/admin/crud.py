import datetime
from new import instancemethod
from django.utils.safestring import mark_safe
from django.utils.html import escape
from dimagi.utils.data.crud import TabularCRUDManager
from dimagi.utils.decorators.memoized import memoized

class ADMAdminCRUDManager(TabularCRUDManager):
    """
       CRUDManager for ADMReports and ADMColumns.
    """
    @property
    def edit_button(self):
        doc_id = self.document_instance.get_id if self.document_instance else ""
        return mark_safe("""<a href="#updateADMItemModal"
            class="btn"
            data-item_id="%s"
            onclick="adm_interface.update_item(this)"
            data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % doc_id)

    @property
    def properties_in_row(self):
        return ["slug", "domain", "name", "description"]

    def _boolean_label(self, value, yes_text="Yes", no_text="No"):
        return mark_safe('<span class="label label-%s">%s</span>' %
                         ("success" if value else "warning", yes_text if value else no_text))

    def format_property(self, key, property):
        if isinstance(property, bool):
            return self._boolean_label(property)
        if key == 'domain':
            return mark_safe('<span class="label label-inverse">%s</span>' % property)\
            if property else "Global Default"
        return super(ADMAdminCRUDManager, self).format_property(key, property)

    def is_valid(self, existing=None, **kwargs):
        slug = kwargs.get('slug')
        domain = kwargs.get('domain')
        existing_doc = self.document_class.get_default(slug, domain=domain, wrap=False)
        if existing:
            return existing.slug == slug or not existing_doc
        return not existing_doc

    def update(self, **kwargs):
        for key, item in kwargs.items():
            try:
                setattr(self.document_instance, key, item)
            except AttributeError:
                pass
        self.document_instance.date_modified = datetime.datetime.utcnow()
        self.document_instance.save()

    def create(self, **kwargs):
        self.document_instance = self.document_class()
        self.update(**kwargs)


class ColumnAdminCRUDManager(ADMAdminCRUDManager):

    def format_property(self, key, property):
        if key == "name":
            return "%s" % property
        return super(ColumnAdminCRUDManager, self).format_property(key, property)


class CouchViewColumnAdminCRUDManager(ColumnAdminCRUDManager):

    @property
    def properties_in_row(self):
        return super(CouchViewColumnAdminCRUDManager, self).properties_in_row + ["couch_view", "key_format"]

    def format_property(self, key, property):
        if key == 'key_format':
            return '[%s]' % escape(property)
        return super(CouchViewColumnAdminCRUDManager, self).format_property(key, property)


class ReducedColumnAdminCRUDManager(CouchViewColumnAdminCRUDManager):

    @property
    def properties_in_row(self):
        return super(ReducedColumnAdminCRUDManager, self).properties_in_row + \
               ["returns_numerical", "ignore_datespan"]


class DaysSinceColumnAdminCRUDManager(CouchViewColumnAdminCRUDManager):

    @property
    def properties_in_row(self):
        return super(DaysSinceColumnAdminCRUDManager, self).properties_in_row + \
               ["property_name", "start_or_end"]

    def format_property(self, key, property):
        if key == "start_or_end":
            from corehq.apps.adm.admin.forms import DATESPAN_CHOICES
            choices = dict(DATESPAN_CHOICES)
            return "%s and %s" % (self.document_instance.property_name, choices.get(property, "--"))
        return super(DaysSinceColumnAdminCRUDManager, self).format_property(key, property)


class ConfigurableColumnAdminCRUDManager(ColumnAdminCRUDManager):

    @property
    def edit_button(self):
        doc_id = self.document_instance.get_id if self.document_instance else ""
        return mark_safe("""<a href="#updateADMItemModal"
            class="btn"
            data-item_id="%s"
            data-form_class="%s"
            onclick="adm_interface.update_item(this)"
            data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" %\
                         (doc_id, "%sForm" % self.document_class.__name__))

    @property
    def properties_in_row(self):
        return ["column_type"] + super(ConfigurableColumnAdminCRUDManager, self).properties_in_row + \
               ["is_configurable", "configurable_properties"]

    @property
    @memoized
    def configurable_properties_in_row(self):
        properties = ['<dl class="dl-horizontal" style="margin:0;padding:0;">']
        for key in self.document_instance.configurable_properties:
            property = getattr(self.document_instance, key)
            properties.append("<dt>%s</dt>" % self.format_key(key))
            properties.append("<dd>%s</dd>" % self.format_property(key, property))
        properties.append("</dl>")
        return mark_safe("\n".join(properties))

    def format_key(self, key):
        return key.replace("_", " ").title()

    def format_property(self, key, property):
        if isinstance(property, instancemethod):
            return property()
        if key == 'configurable_properties':
            return self.configurable_properties_in_row
        return super(ConfigurableColumnAdminCRUDManager, self).format_property(key, property)


class CompareColumnAdminCRUDManager(ConfigurableColumnAdminCRUDManager):

    def format_key(self, key):
        if key == "numerator_ref" or key == "denominator_ref":
            return key.replace("_ref", "").title()
        return super(CompareColumnAdminCRUDManager, self).format_key(key)

    def format_property(self, key, property):
        if key == "numerator_ref" or key == 'denominator_ref':
            try:
                col = getattr(self.document_instance, key.replace('_ref', ''))
                configurable = '<span class="label label-success">Configurable</span><br />'
                return mark_safe('%s %s(%s)' %\
                                 (col.name, configurable if col.is_configurable else '', property))
            except Exception:
                return "Ref Not Found (%s)" % property
        return super(CompareColumnAdminCRUDManager, self).format_property(key, property)


class CaseCountColumnCRUDManager(ConfigurableColumnAdminCRUDManager):

    def format_property(self, key, property):
        if key == 'inactivity_milestone':
            return "%s days" % property if property else "N/A"
        if key == 'ignore_datespan' and self.document_instance.inactivity_milestone > 0:
            return 'N/A'
        if key == 'filter_option':
            from corehq.apps.adm.models import CASE_FILTER_OPTIONS
            filter_options = dict(CASE_FILTER_OPTIONS)
            return filter_options[property or '']
        if key == 'case_types':
            return ", ".join(property) if property and property[0] else 'N/A'
        if key == 'case_status':
            from corehq.apps.adm.models import CASE_STATUS_OPTIONS
            case_status_options = dict(CASE_STATUS_OPTIONS)
            return case_status_options[property or '']
        return super(CaseCountColumnCRUDManager, self).format_property(key, property)


class ADMReportCRUDManager(ADMAdminCRUDManager):

    @property
    def properties_in_row(self):
        return ["reporting_section"] + super(ADMReportCRUDManager, self).properties_in_row +\
               ["column_refs", "key_type"]

    def format_property(self, key, property):
        if key == 'column_refs':
            ol = ['<ol>']
            for ref in property:
                from corehq.apps.adm.models import BaseADMColumn
                if self.document_instance.is_default:
                    col = BaseADMColumn.get_default(ref)
                else:
                    col = BaseADMColumn.get_correct_wrap(ref)
                if col:
                    ol.append('<li>%s <span class="label label-info">%s</span></li>' % (col.name, col.slug))
            ol.append('</ol>')
            return  mark_safe("\n".join(ol))
        if key == 'reporting_section':
            from corehq.apps.adm.models import REPORT_SECTION_OPTIONS
            sections = dict(REPORT_SECTION_OPTIONS)
            return sections.get(property, "Unknown")
        return super(ADMReportCRUDManager, self).format_property(key, property)

