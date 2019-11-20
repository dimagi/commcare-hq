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


class OpenDisabilityTypeSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_disability_type")
    expression = "closed_on IS NULL AND disability_type ~ ?"


class OpenFemaleDisabledSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_disabled")
    expression = "closed_on IS NULL AND sex = 'F' and disabled = 1"


class OpenFemaleHHCasteSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_caste")
    expression = "closed_on IS NULL AND sex = 'F' and hh_caste = ?"


class OpenFemaleHHCasteNotSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_caste_not")
    expression = "closed_on IS NULL AND sex = 'F' and hh_caste NOT IN (?, ?)"


class OpenFemaleHHMinoritySpec(SumWhenTemplateSpec):
    type = TypeProperty("open_female_hh_minority")
    expression = "closed_on IS NULL AND sex = 'F' and hh_minority = 1"


class OpenMaleDisabledSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_disabled")
    expression = "closed_on IS NULL AND sex = IN ('M', 'O') and disabled = 1"


class OpenMaleHHCasteSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_caste")
    expression = "closed_on IS NULL AND sex IN ('M', 'O') and hh_caste = ?"


class OpenMaleHHCasteNotSpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_caste_not")
    expression = "closed_on IS NULL AND sex in ('M', 'O') and hh_caste NOT IN (?, ?)"


class OpenMaleHHMinoritySpec(SumWhenTemplateSpec):
    type = TypeProperty("open_male_hh_minority")
    expression = "closed_on IS NULL AND sex in ('M', 'O') and hh_minority = 1"
