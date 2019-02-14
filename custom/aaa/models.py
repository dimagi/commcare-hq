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

    @classmethod
    def agg_from_village_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-village_location')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            sc_id = village.sc_id,
            phc_id = village.phc_id,
            taluka_id = village.taluka_id,
            district_id = village.district_id,
            state_id = village.state_id
        FROM (
            SELECT doc_id, sc_id, phc_id, taluka_id, district_id, state_id
            FROM "{village_location_ucr_tablename}"
        ) village
        WHERE child.village_id = village.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            village_location_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_awc_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-awc_location')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            supervisor_id = awc.supervisor_id,
            block_id = awc.block_id
        FROM (
            SELECT doc_id, supervisor_id, block_id
            FROM "{awc_location_ucr_tablename}"
        ) awc
        WHERE child.awc_id = awc.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            awc_location_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}


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

    @classmethod
    def agg_from_person_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-person_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{woman_tablename}" AS child (
            domain, household_case_id, person_case_id, opened_on, closed_on,
            dob, marital_status, sex, migration_status
        ) (
            SELECT
                %(domain)s,
                person.household_case_id,
                person.doc_id,
                person.opened_on,
                person.closed_on,
                person.dob,
                person.marital_status,
                person.sex,
                person.migration_status
            FROM "{person_cases_ucr_tablename}" person
            WHERE sex = 'F' AND date_part('year', age(dob)) BETWEEN 15 AND 49
        )
        ON CONFLICT (person_case_id) DO UPDATE SET
           closed_on = EXCLUDED.closed_on
        """.format(
            woman_tablename=cls._meta.db_table,
            person_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_household_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-household_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            awc_id = household.awc_owner_id,
            village_id = household.village_owner_id
        FROM (
            SELECT
                doc_id,
                awc_owner_id,
                village_owner_id
            FROM "{household_cases_ucr_tablename}"
        ) household
        WHERE child.household_case_id = household.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            household_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}


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

    household_case_id = models.TextField(null=True)
    person_case_id = models.TextField()
    ccs_record_case_id = models.TextField(primary_key=True)

    opened_on = models.DateField()
    closed_on = models.DateField(null=True)
    hrp = models.TextField(help_text="High Risk Pregnancy", null=True)
    child_birth_location = models.TextField(null=True)
    edd = models.DateField(null=True)
    add = models.DateField(null=True)

    @classmethod
    def agg_from_ccs_record_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{ccs_reccord_tablename}" AS ccs_record (
            domain, person_case_id, ccs_record_case_id, opened_on, closed_on,
            hrp, child_birth_location, add, edd
        ) (
            SELECT
                %(domain)s,
                person_case_id,
                doc_id,
                opened_on,
                closed_on,
                hrp,
                child_birth_location,
                edd,
                add
            FROM "{ccs_record_cases_ucr_tablename}" ccs_record_ucr
        )
        ON CONFLICT (person_case_id) DO UPDATE SET
           closed_on = EXCLUDED.closed_on
        """.format(
            woman_tablename=cls._meta.db_table,
            ccs_record_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_person_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-person_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            household_case_id = person.household_case_id
        FROM (
            SELECT household_case_id,
            FROM "{person_cases_ucr_tablename}"
        ) person
        WHERE child.person_case_id = person.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            person_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_household_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-household_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            awc_id = household.awc_owner_id,
            village_id = household.village_owner_id
        FROM (
            SELECT
                doc_id,
                awc_owner_id,
                village_owner_id
            FROM "{household_cases_ucr_tablename}"
        ) household
        WHERE child.household_case_id = household.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            household_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}


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
    closed_on = models.DateField(help_text="child_health.closed_on", null=True)

    dob = models.DateField(null=True)
    sex = models.TextField(null=True)
    migration_status = models.TextField(null=True)

    @classmethod
    def agg_from_child_health_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-child_health_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{child_tablename}" AS child (
            domain, person_case_id, child_health_case_id, opened_on, closed_on
        ) (
            SELECT
                %(domain)s AS domain,
                child_health.person_case_id AS person_case_id,
                child_health.doc_id AS child_health_case_id,
                child_health.opened_on AS opened_on,
                child_health.closed_on AS closed_on
            FROM "{child_health_cases_ucr_tablename}" child_health
        )
        ON CONFLICT (person_case_id) DO UPDATE SET
           closed_on = EXCLUDED.closed_on
        """.format(
            child_tablename=cls._meta.db_table,
            child_health_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_person_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-person_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            household_case_id = person.household_case_id,
            dob = person.dob,
            sex = person.sex,
            migration_status = person.migration_status
        FROM (
            SELECT
                household_case_id,
                doc_id,
                dob,
                sex,
                migration_status
            FROM "{person_cases_ucr_tablename}"
        ) person
        WHERE child.person_case_id = person.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            person_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_household_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-household_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            awc_id = household.awc_owner_id,
            village_id = household.village_owner_id
        FROM (
            SELECT
                doc_id,
                awc_owner_id,
                village_owner_id
            FROM "{household_cases_ucr_tablename}"
        ) household
        WHERE child.household_case_id = household.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            household_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}


class AggregationInformation(models.Model):
    """Used to track the performance and timings of our data aggregations"""

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    end_time = models.DateTimeField(null=True, help_text="Time the aggregation completed")

    domain = models.TextField()
    step = models.TextField(help_text="Slug for the step of the aggregation")
    aggregation_window_start = models.DateTimeField()
    aggregation_window_end = models.DateTimeField()
