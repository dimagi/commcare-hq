from couchforms.models import XFormInstance
from django.conf import settings


def get_all_forms_in_all_domains():
    assert settings.UNIT_TESTING, (
        'You can only call {} when unit testing'
        .format(get_all_forms_in_all_domains.__name__)
    )
    return XFormInstance.view(
        'hqadmin/forms_over_time',
        reduce=False,
        include_docs=True,
    ).all()


def get_number_of_forms_in_all_domains():
    return XFormInstance.view('hqadmin/forms_over_time').one()['value']
