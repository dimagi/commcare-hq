from django import forms


class TaskCreationForm(forms.Form):
    question_ids = forms.CharField(
        widget=forms.Textarea,
        label="Enter Question ids, one per line"
    )
