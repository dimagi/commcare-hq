from django.utils.translation import ugettext as _


def validate_report_parameters(parameters, config):
    for parameter in parameters:
        if not parameter in config:
            raise KeyError(_("Parameter '%s' is missing" % parameter))
