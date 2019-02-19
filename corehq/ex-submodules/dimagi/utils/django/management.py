from __future__ import absolute_import
from __future__ import unicode_literals
import csv342 as csv
from django.http import HttpResponse

from dimagi.utils.parsing import string_to_boolean
from six.moves import input
import six


def are_you_sure(prompt="Are you sure you want to proceed? (yes or no): "):
    """
    Ask a user if they are sure before doing something.  Return
    whether or not they are sure
    """
    should_proceed = input(prompt)
    try:
        return string_to_boolean(should_proceed)
    except Exception:
        return False


def export_as_csv_action(description="Export selected objects as CSV file",
                         fields=None, exclude=None, header=True):
    """
    Include this in ModelAdmin.actions to get an option of export as CSV in Django Admin.

    copied from https://djangosnippets.org/snippets/2369/

    This function returns an export csv action
    'fields' and 'exclude' work like in django ModelForm
    'header' is whether or not to output the column names as the first row
    """

    def export_as_csv(modeladmin, request, queryset):
        """
        Generic csv export admin action.
        based on http://djangosnippets.org/snippets/1697/
        """
        opts = modeladmin.model._meta
        field_names = set(field.name for field in opts.fields)
        if fields:
            fieldset = set(fields)
            field_names = field_names & fieldset
        elif exclude:
            excludeset = set(exclude)
            field_names = field_names - excludeset

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=%s.csv' % six.text_type(opts).replace('.', '_')

        writer = csv.writer(response)
        if header:
            writer.writerow(list(field_names))
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])
        return response

    export_as_csv.short_description = description
    return export_as_csv
