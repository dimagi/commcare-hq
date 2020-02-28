import json

from django.utils.translation import ugettext as _

from jsonobject.exceptions import BadValueError

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.transforms.specs import TRANSFORM_SPEC_MAP


class TransformFactory(object):
    @classmethod
    def get_transform(cls, spec):
        try:
            return TRANSFORM_SPEC_MAP[spec['type']].wrap(spec)
        except KeyError:
            raise BadSpecError(_('Invalid or missing transform type: {}. Valid options are: {}').format(
                spec.get('type', None),
                ', '.join(TRANSFORM_SPEC_MAP),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating transform: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))
