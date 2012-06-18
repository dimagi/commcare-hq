from django import forms
from corehq.apps.domain.models import Domain
import re
from corehq.apps.domain.utils import new_domain_re

class AddReviewForm(forms.Form):

    review_rating = forms.IntegerField(max_value=5, min_value=0)
    review_title = forms.CharField(label="Title", max_length=35)
    review_info = forms.CharField(label="Review (Optional)", max_length=500, required=False)
