from django import forms
from corehq.apps.domain.models import Domain
import re
from corehq.apps.domain.utils import new_domain_re
from corehq.apps.orgs.models import Organization

class AddReviewForm(forms.Form):

    review_rating = forms.IntegerField(max_value=5, min_value=0, help_text="Rate this app on a scale of 0 to 5")
    review_name = forms.CharField(label="nickname", max_length=25)
    review_title = forms.CharField(label="Title", max_length=35)
    review_info = forms.CharField(label="Review (Optional)", max_length=500, required=False)

    def clean_review_name(self):
        data = self.cleaned_data['review_name'].strip()
        return data

    def clean_review_info(self):
        data = self.cleaned_data['review_info']
        return data

    def clean_review_rating(self):
      data = self.cleaned_data['review_rating']
      return data

    def clean_review_title(self):
      data = self.cleaned_data['review_title']
      return data

    def clean(self):
        for field in self.cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                self.cleaned_data[field] = self.cleaned_data[field].strip()
        return self.cleaned_data

