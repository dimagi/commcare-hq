from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms


class TaskCreationForm(forms.Form):
    question_ids = forms.CharField(
        widget=forms.Textarea,
        label="Enter Question ids, one per line"
    )
