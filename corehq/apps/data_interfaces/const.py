from django.utils.translation import gettext_lazy

CRITERIA_OPERATOR_CHOICES = [
    ('ALL', gettext_lazy('ALL of the criteria are met')),
    ('ANY', gettext_lazy('ANY of the criteria are met')),
]
