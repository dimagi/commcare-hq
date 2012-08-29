from django import forms
from corehq.apps.domain.models import Domain
import re
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.orgs.models import Organization

class AddReviewForm(forms.Form):

    review_title = forms.CharField(label="Title", max_length=35)
    review_info = forms.CharField(label="Review (Optional)", max_length=500, required=False, widget=forms.Textarea)

    def clean_review_info(self):
        data = self.cleaned_data['review_info']
        return data

    def clean_review_rating(self):
        data = int(self.cleaned_data['review_rating'])
        if data < 1:
            data = 1
        if data > 5:
            data = 5
        return data

    def clean_review_title(self):
        data = self.cleaned_data['review_title']
        return data

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data
