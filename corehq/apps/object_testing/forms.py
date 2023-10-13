from crispy_forms import layout as crispy
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.object_testing.models import ObjectTest, ContextFactoryChoices
from corehq.apps.userreports.models import UCRExpression


class TestModelChoices(TextChoices):
    ucr_expression = 'ucrexpression', _("Filters and Expressions")


class ObjectTestCreateForm(forms.Form):
    fieldset_title = _('Create a new test')

    name = forms.CharField()
    description = forms.CharField(widget=forms.TextInput())
    test_model_type = forms.ChoiceField(choices=TestModelChoices.choices)
    test_model_id = forms.ChoiceField()

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = request.domain
        self.fields['test_model_id'].choices = [
            (expr.id, expr.name)
            for expr in UCRExpression.objects.filter(domain=self.domain)
        ]
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                self.fieldset_title,
                crispy.Field('name'),
                crispy.Field('description'),
                crispy.Field('test_model_type'),
                crispy.Field('test_model_id'),
            )
        )
        self.helper.render_required_fields = True
        self.add_to_helper()

    def add_to_helper(self):
        self.helper.add_input(
            crispy.Submit('submit', _('Create'))
        )

    def save(self):
        content_type = ContentType.objects.get(model=self.cleaned_data['test_model_type'])
        test_obj = content_type.get_object_for_this_type(id=self.cleaned_data['test_model_id'])
        return ObjectTest.objects.create(
            domain=self.domain,
            name=self.cleaned_data['name'],
            description=self.cleaned_data['description'],
            content_type=content_type,
            content_object=test_obj
        )


class ObjectTestUpdateForm(ObjectTestCreateForm):
    fieldset_title = _('Update Test')

    context_factory = forms.ChoiceField(choices=ContextFactoryChoices.choices)
    input = forms.JSONField()
    expected = forms.JSONField()

    def __init__(self, request, instance, *args, **kwargs):
        self.instance = instance
        kwargs['initial'] = {
            'name': instance.name,
            'description': instance.description,
            'test_model_type': instance.content_type.model,
            'test_model_id': instance.object_id,
            'context_factory': instance.context_factory,
            'input': instance.input,
            'expected': instance.expected,
        }
        super().__init__(request, *args, **kwargs)

    def add_to_helper(self):
        self.helper.form_tag = False

    def save(self):
        content_type = ContentType.objects.get(model=self.cleaned_data['test_model_type'])
        test_obj = content_type.get_object_for_this_type(id=self.cleaned_data['test_model_id'])
        self.instance.name = self.cleaned_data['name']
        self.instance.description = self.cleaned_data['description']
        self.instance.content_type = content_type
        self.instance.content_object = test_obj
        self.instance.context_factory = self.cleaned_data['context_factory']
        self.instance.input = self.cleaned_data['input']
        self.instance.expected = self.cleaned_data['expected']
        self.instance.save()
        return self.instance
