import json
from django.utils.translation import ugettext as _
from jsonobject.exceptions import BadValueError
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.specs import PropertyNameGetterSpec, PropertyPathGetterSpec


class ExpressionFactory(object):
    spec_map = {
        'property_name': PropertyNameGetterSpec,
        'property_path': PropertyPathGetterSpec,
    }

    @classmethod
    def from_spec(cls, spec):
        try:
            return cls.spec_map[spec['type']].wrap(spec).getter
        except KeyError:
            raise BadSpecError(_('Invalid getter type: {}. Valid options are: {}').format(
                spec['type'],
                ', '.join(cls.spec_map.keys()),
            ))
        except BadValueError as e:
            raise BadSpecError(_('Problem creating getter: {}. Message is: {}').format(
                json.dumps(spec, indent=2),
                str(e),
            ))
