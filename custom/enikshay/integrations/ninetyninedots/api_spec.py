from __future__ import absolute_import

import os

import jsonobject
import yaml

from custom.enikshay.const import SECTORS
from dimagi.ext.jsonobject import StrictJsonObject
from dimagi.utils.decorators.memoized import memoized


class DotsApiSectorParam(StrictJsonObject):
    public = jsonobject.StringProperty()
    private = jsonobject.StringProperty()
    both = jsonobject.StringProperty()

    def __init__(self, *args, **kwargs):
        try:
            _obj = args[0]
        except IndexError:
            _obj = {}
        _obj.update(kwargs)

        if _obj:
            if "both" in _obj and ("public" in _obj or "private" in _obj):
                raise ValueError("Can't define 'public' or 'private' options with 'both'")
            if "both" not in _obj and len(set(("public", "private")) - set(_obj.keys())) > 0:
                raise ValueError("Must contain both public and private options")

        return super(DotsApiSectorParam, self).__init__(*args, **kwargs)


class DotsApiParamChoices(DotsApiSectorParam):
    public = jsonobject.ListProperty()
    private = jsonobject.ListProperty()
    both = jsonobject.ListProperty()


class DotsApiParam(StrictJsonObject):
    api_param_name = jsonobject.StringProperty(required=True)
    required_ = jsonobject.BooleanProperty(default=False, name='required')
    choices = jsonobject.ObjectProperty(DotsApiParamChoices)
    case_type = jsonobject.ObjectProperty(DotsApiSectorParam)
    case_property = jsonobject.ObjectProperty(DotsApiSectorParam)


class DotsApiParams(StrictJsonObject):
    api_params = jsonobject.ListProperty(DotsApiParam)


@memoized
def load_api_spec():
    """Loads API spec from api_properties.yaml and validates that the spec is correct
    """
    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_properties.yaml')
    with open(filename, 'r') as f:
        spec = DotsApiParams(yaml.load(f))
    return spec


def get_payload_properties(sector):
    if sector not in SECTORS:
        raise ValueError('sector argument should be one of {}'.format(",".join(SECTORS)))

    properties = {}
    spec = load_api_spec()
    for param in spec.api_params:
        choices = getattr(param.choices, sector) or param.choices.both
        properties[param.api_param_name] = jsonobject.StringProperty(
            choices=choices,
            required=param.required_,
            exclude_if_none=True,
        )
    return properties


PublicPatientPayload = type('PublicPatientPayload', (StrictJsonObject,),
                            get_payload_properties('public'))

PrivatePatientPayload = type('PublicPatientPayload', (StrictJsonObject,),
                             get_payload_properties('private'))
