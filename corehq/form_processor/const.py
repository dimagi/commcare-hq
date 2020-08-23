from django.conf import settings

from dimagi.utils.modules import to_function


XFORM_PRE_PROCESSORS = {
    domain: [to_function(class_name) for class_name in preprocessors]
    for domain, preprocessors in settings.XFORM_PRE_PROCESSORS.items()
}
