"""Contains all models for the AAA Convergence Dashboard.

Conventions followed in this file:
    * Fields ending in _ranges represent a field's history from forms that are useful for filtering.
      This is only used for fields that are required to filter for specific ranges (usually a date range).
    * Fields ending in _history represent a field's entire history from forms.
      They are saved with the format [[date, value], [date, value]].
      They are not guaranteed to be ordered by date.
      They are not intended to be queried on, their interpretation should happen in python.
      These history fields are saved in a separate model to ensure that the main model stays
      fast and small for filtering.
    * Each model contains all parts of the location hierarchy.
    * Each model should support a future world where it is being accessed in a
      sharded database (CitusDB).
"""

from __future__ import absolute_import, unicode_literals

from django.contrib.postgres.fields import ArrayField, DateRangeField
from django.db import models

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name


class LocationDenormalizedModel(models.Model):
    """Abstract base model for containing all the location fields necessary for querying."""

    # support multiple domains so QA is easier
    domain = models.TextField(null=False)

    # Shared location hierarchy
    state_id = models.TextField(null=True)
    district_id = models.TextField(null=True)

    # CAS Hierarchy
    block_id = models.TextField(null=True)
    supervisor_id = models.TextField(null=True)
    awc_id = models.TextField(null=True)

    # AAA/MoH Hierarchy
    taluka_id = models.TextField(null=True)
    phc_id = models.TextField(null=True)
    sc_id = models.TextField(null=True)
    village_id = models.TextField(null=True)

    class Meta(object):
        abstract = True


class Woman(LocationDenormalizedModel):
    """Represents a woman registered in the AAA Convergence program.

    This woman may have an eligible_couple or ccs_record case associated with her.
    ccs_record data will be attached to the CcsRecord model.
    """

    household_case_id = models.TextField(null=True)
    person_case_id = models.TextField(primary_key=True)

    opened_on = models.DateField()
    closed_on = models.DateField(null=True)
    pregnant_ranges = ArrayField(
        DateRangeField(),
        help_text="The ranges in which a ccs_record has been opened and the baby has not been born",
        null=True
    )
    dob = models.DateField(null=True)
    marital_status = models.TextField(null=True)
    sex = models.TextField(null=True)
    migration_status = models.TextField(null=True)

    fp_current_method_ranges = ArrayField(
        DateRangeField(),
        help_text="Ranges of time when eligible_couple.fp_current_method != 'none'",
        null=True
    )


class WomanHistory(models.Model):
    """The history of form properties for any woman registered."""

    person_case_id = models.TextField(primary_key=True)

    # eligible_couple properties
    fp_current_method_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    fp_preferred_method_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)


class CcsRecord(LocationDenormalizedModel):
    """Represent a single pregnancy, lactation, and complementary feeding schedule for a Woman.

    Lactation is tracked 6 months after the delivery of the child.
    Complementary feeding is tracked until the child is 2 years old

    A Woman will likely have many pregnancies over her lifetime.
    If a Woman becomes pregnant within two years of a child being born, she will have two ccs_record cases.
    If a Woman has twins and those twins are registered in the program before birth,
        she will have one ccs_record for this pregnancy.
    If a Woman has twins and those twins are not registered in the program before birth,
        she will have two ccs_records for this pregnancy
    """

    person_case_id = models.TextField()
    ccs_record_case_id = models.TextField(primary_key=True)

    opened_on = models.DateField()
    closed_on = models.DateField(null=True)
    hrp = models.TextField(help_text="High Risk Pregnancy", null=True)
    child_birth_location = models.TextField(null=True)
    edd = models.DateField(null=True)
    add = models.DateField(null=True)


class Child(LocationDenormalizedModel):
    """Represents a child registered in the AAA Convergence program.

    This beneficiary will have a child_health case associated with it.
    """

    household_case_id = models.TextField(null=True)
    # need to investigate that there is not an app workflow or error state
    # where a person has multiple child_health cases
    person_case_id = models.TextField(unique=True)
    child_health_case_id = models.TextField(primary_key=True)

    # For now, these should be the same between child_health and person case
    # but going with child_health as there's a potential for person case to live
    # on after the child_health case stops being tracked (into adolescent girl, or woman)
    opened_on = models.DateField(help_text="child_health.opened_on")
    closed_on = models.DateField(help_text="child_health.opened_on", null=True)

    dob = models.DateField(null=True)
    sex = models.TextField(null=True)
    migration_status = models.TextField(null=True)


class AggregationInformation(models.Model):
    """Used to track the performance and timings of our data aggregations"""

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    end_time = models.DateTimeField(null=True, help_text="Time the aggregation completed")

    domain = models.TextField()
    step = models.TextField(help_text="Slug for the step of the aggregation")
    aggregation_window_start = models.DateTimeField()
    aggregation_window_end = models.DateTimeField()
