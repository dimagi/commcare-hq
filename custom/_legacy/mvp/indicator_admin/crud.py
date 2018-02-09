from __future__ import absolute_import
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.indicators.admin.crud import CouchIndicatorCRUDManager


class MVPActiveCasesCRUDManager(CouchIndicatorCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(MVPActiveCasesCRUDManager, self).properties_in_row
        return original_props[:6] + ["case_type"] + original_props[-3:]


class MVPChildCasesByAgeCRUDManager(MVPActiveCasesCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(MVPChildCasesByAgeCRUDManager, self).properties_in_row
        return original_props[:7] + ["is_dob_in_datespan", "show_active_only"] + original_props[-3:]

    def format_property(self, key, property):
        if key == "is_dob_in_datespan":
            return mark_safe(render_to_string("mvp/partials/age_restriction_summary.html", {
                "max_age_in_days": self.document_instance.max_age_in_days,
                "min_age_in_days": self.document_instance.min_age_in_days,
                "is_dob_in_datespan": self.document_instance.is_dob_in_datespan,
            }))
        if key == "show_active_only":
            return mark_safe(render_to_string("indicators/partials/yes_no.html", {
                "property": property
            }))
        if key == "case_type":
            return property or mark_safe('<span class="label label-default">default: child</span>')
        return super(MVPChildCasesByAgeCRUDManager, self).format_property(key, property)

