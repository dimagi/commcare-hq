import re

from dimagi.ext.jsonobject import (
    IntegerProperty,
    JsonObject,
    ListProperty,
    StringProperty,
)

from corehq.apps.userreports.specs import TypeProperty


class SumWhenTemplateSpec(JsonObject):
    type = StringProperty(required=True)
    expression = StringProperty(required=True)
    binds = ListProperty()
    then = IntegerProperty()

    def bind_count(self):
        return len(re.sub(r'[^?]', '', self.expression))


### Templates for testing

class YearRangeTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty('year_range')
    expression = "year >= ? and year < ?"


class UnderXMonthsTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("under_x_months")
    expression = "age_at_registration < ?"


### Templates for ICDS

class ClosedOnNullTemplateSpec(SumWhenTemplateSpec):
    type = TypeProperty("closed_on_null")
    expression = "closed_on IS NULL"


class OpenFemaleHHCasteSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_caste")
    expression = "closed_on IS NULL AND sex = 'F' and hh_caste = ?"
