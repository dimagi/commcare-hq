import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.transforms.specs import CustomTransform, DateFormatTransform, NumberFormatTransform


class TransformFactory(object):
    spec_map = {
        'custom': CustomTransform,
        'date_format': DateFormatTransform,
        'number_format': NumberFormatTransform,
    }

    @classmethod
    def get_transform(cls, spec):
        try:
            return cls.spec_map[spec['type']].wrap(spec)
        except KeyError:
            raise BadSpecError(_('Invalid or missing transform type: {}. Valid options are: {}').format(
                spec.get('type', None),
                ', '.join(cls.spec_map.keys()),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating transform: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))
