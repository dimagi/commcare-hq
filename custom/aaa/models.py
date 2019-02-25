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
from django.utils.decorators import classproperty

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

    # person case properties
    opened_on = models.DateField()
    closed_on = models.DateField(null=True)
    pregnant_ranges = ArrayField(
        DateRangeField(),
        help_text="The ranges in which a ccs_record has been opened and the baby has not been born",
        null=True
    )
    name = models.TextField(null=True)
    dob = models.DateField(null=True)
    marital_status = models.TextField(null=True)
    sex = models.TextField(null=True)
    migration_status = models.TextField(null=True)
    age_marriage = models.PositiveIntegerField(null=True)
    has_aadhar_number = models.NullBooleanField()
    husband_name = models.TextField(null=True)
    contact_phone_number = models.TextField(null=True)
    num_male_children_died = models.TextField(null=True)
    num_female_children_died = models.TextField(null=True)
    blood_group = models.TextField(null=True)

    # household properties
    hh_address = models.TextField(null=True)
    hh_religion = models.TextField(null=True)
    hh_caste = models.TextField(null=True)
    hh_bpl_apl = models.TextField(null=True)

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
            name, dob, marital_status, sex, migration_status, age_marriage,
            has_aadhar_number, husband_name, contact_phone_number,
            num_male_children_died, num_female_children_died, blood_group
        ) (
            SELECT
                %(domain)s,
                household_case_id,
                doc_id,
                opened_on,
                closed_on,
                name,
                dob,
                marital_status,
                sex,
                migration_status,
                age_marriage,
                aadhar_number IS NOT NULL and aadhar_number != '' AS has_aadhar_number,
                husband_name,
                contact_phone_number,
                num_male_children_died,
                num_female_children_died,
                blood_group
            FROM "{person_cases_ucr_tablename}" person
            WHERE sex = 'F' AND date_part('year', age(dob)) BETWEEN 15 AND 49
        )
        ON CONFLICT (person_case_id) DO UPDATE SET
           closed_on = EXCLUDED.closed_on,
           name = EXCLUDED.name,
           dob = EXCLUDED.dob,
           marital_status = EXCLUDED.marital_status,
           sex = EXCLUDED.sex,
           migration_status = EXCLUDED.migration_status,
           age_marriage = EXCLUDED.age_marriage,
           has_aadhar_number = EXCLUDED.has_aadhar_number,
           husband_name = EXCLUDED.husband_name,
           contact_phone_number = EXCLUDED.contact_phone_number,
           num_male_children_died = EXCLUDED.num_male_children_died,
           num_female_children_died = EXCLUDED.num_female_children_died,
           blood_group = EXCLUDED.blood_group
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
            village_id = household.village_owner_id,
            hh_address = household.hh_address,
            hh_religion = household.hh_religion,
            hh_caste = household.hh_caste,
            hh_bpl_apl = household.hh_bpl_apl
        FROM (
            SELECT
                doc_id,
                awc_owner_id,
                village_owner_id,
                hh_address,
                hh_religion,
                hh_caste,
                hh_bpl_apl
            FROM "{household_cases_ucr_tablename}"
        ) household
        WHERE child.household_case_id = household.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            household_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_ccs_record_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{woman_tablename}" AS woman SET
            pregnant_ranges = ccs_record.pregnant_ranges
        FROM (
            SELECT person_case_id, array_agg(pregnant_range) as pregnant_ranges
            FROM(
                SELECT person_case_id,
                       daterange(opened_on::date, add, '[]') as pregnant_range
                FROM "{ccs_record_cases_ucr_tablename}"
                WHERE opened_on < add OR add IS NULL
                GROUP BY person_case_id, pregnant_range
            ) AS _tmp_table
            GROUP BY person_case_id
        ) ccs_record
        WHERE woman.person_case_id = ccs_record.person_case_id
        """.format(
            woman_tablename=cls._meta.db_table,
            ccs_record_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_eligible_couple_forms_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-eligible_couple_forms')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{woman_tablename}" AS woman SET
            fp_current_method_ranges = eligible_couple_fp.fp_current_method_ranges
        FROM (
            SELECT person_case_id, array_agg(fp_current_method_range) AS fp_current_method_ranges
            FROM (
                SELECT person_case_id, fp_current_method, daterange(timeend::date, next_timeend::date) AS fp_current_method_range
                FROM(
                    SELECT person_case_id,
                           fp_current_method,
                           timeend,
                           LEAD(fp_current_method) OVER w AS next_fp_current_method,
                           LEAD(timeend) OVER w AS next_timeend
                    FROM "{eligible_couple_ucr_tablename}"
                    WINDOW w AS (PARTITION BY person_case_id ORDER BY timeend DESC)
                ) AS _tmp_table
            ) eligible_couple
            WHERE fp_current_method != 'none'
            GROUP BY person_case_id
        ) AS eligible_couple_fp
        WHERE woman.person_case_id = eligible_couple_fp.person_case_id
        """.format(
            woman_tablename=cls._meta.db_table,
            eligible_couple_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classproperty
    def aggregation_queries(self):
        return [
            self.agg_from_person_case_ucr,
            self.agg_from_household_case_ucr,
            self.agg_from_ccs_record_case_ucr,
            self.agg_from_eligible_couple_forms_ucr,
            self.agg_from_village_ucr,
            self.agg_from_awc_ucr,
        ]


class WomanHistory(models.Model):
    """The history of form properties for any woman registered."""

    person_case_id = models.TextField(primary_key=True)

    # eligible_couple properties
    fp_current_method_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    fp_preferred_method_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)

    family_planning_form_history = ArrayField(
        models.DateField(), null=True,
        help_text="timeEnd from Family Planning forms submitted against this case"
    )

    @classmethod
    def agg_from_eligible_couple_forms_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-eligible_couple_forms')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{woman_history_tablename}" AS woman (
            person_case_id, fp_current_method_history, fp_preferred_method_history, family_planning_form_history
        ) (
            SELECT person_case_id,
                   array_agg(fp_current_method) AS fp_current_method_history,
                   array_agg(fp_preferred_method) AS fp_preferred_method_history,
                   array_agg(timeend) AS family_planning_form_history
            FROM (
                SELECT person_case_id,
                       timeend,
                       ARRAY[timeend::text, fp_current_method] AS fp_current_method,
                       ARRAY[timeend::text, fp_preferred_method] AS fp_preferred_method
                FROM "{eligible_couple_ucr_tablename}"
            ) eligible_couple
            GROUP BY person_case_id
        )
        ON CONFLICT (person_case_id) DO UPDATE SET
           fp_current_method_history = EXCLUDED.fp_current_method_history,
           fp_preferred_method_history = EXCLUDED.fp_preferred_method_history,
           family_planning_form_history = EXCLUDED.family_planning_form_history
        """.format(
            woman_history_tablename=cls._meta.db_table,
            eligible_couple_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classproperty
    def aggregation_queries(cls):
        return [
            cls.agg_from_eligible_couple_forms_ucr,
        ]


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
    lmp = models.DateField(null=True)
    preg_reg_date = models.DateField(null=True)
    woman_weight_at_preg_reg = models.DecimalField(null=True, max_digits=6, decimal_places=2)

    @classmethod
    def agg_from_ccs_record_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-ccs_record_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{ccs_record_tablename}" AS ccs_record (
            domain, person_case_id, ccs_record_case_id, opened_on, closed_on,
            hrp, child_birth_location, add, edd, lmp, preg_reg_date, woman_weight_at_preg_reg
        ) (
            SELECT
                %(domain)s,
                person_case_id,
                doc_id,
                opened_on,
                closed_on,
                hrp,
                child_birth_location,
                add,
                edd,
                lmp,
                preg_reg_date,
                woman_weight_at_preg_reg
            FROM "{ccs_record_cases_ucr_tablename}" ccs_record_ucr
        )
        ON CONFLICT (ccs_record_case_id) DO UPDATE SET
           closed_on = EXCLUDED.closed_on,
           hrp = EXCLUDED.hrp,
           child_birth_location = EXCLUDED.child_birth_location,
           add = EXCLUDED.add,
           edd = EXCLUDED.edd,
           lmp = EXCLUDED.lmp,
           preg_reg_date = EXCLUDED.preg_reg_date,
           woman_weight_at_preg_reg = EXCLUDED.woman_weight_at_preg_reg
        """.format(
            ccs_record_tablename=cls._meta.db_table,
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
            SELECT doc_id, household_case_id
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

    @classproperty
    def aggregation_queries(self):
        return [
            self.agg_from_ccs_record_case_ucr,
            self.agg_from_person_case_ucr,
            self.agg_from_household_case_ucr,
            self.agg_from_village_ucr,
            self.agg_from_awc_ucr,
        ]


class Child(LocationDenormalizedModel):
    """Represents a child registered in the AAA Convergence program.

    This beneficiary will have a child_health case associated with it.
    """

    household_case_id = models.TextField(null=True)
    # need to investigate that there is not an app workflow or error state
    # where a person has multiple child_health cases
    person_case_id = models.TextField(unique=True)
    child_health_case_id = models.TextField(primary_key=True)
    mother_case_id = models.TextField(null=True)
    tasks_case_id = models.TextField(null=True)

    # For now, these should be the same between child_health and person case
    # but going with child_health as there's a potential for person case to live
    # on after the child_health case stops being tracked (into adolescent girl, or woman)
    opened_on = models.DateField(help_text="child_health.opened_on")
    closed_on = models.DateField(help_text="child_health.closed_on", null=True)

    # child_health properties
    birth_weight = models.PositiveIntegerField(null=True, help_text="birth weight in grams")
    breastfed_within_first = models.TextField(null=True)
    is_exclusive_breastfeeding = models.TextField(null=True)
    comp_feeding = models.TextField(null=True)
    diet_diversity = models.TextField(null=True)
    diet_quantity = models.TextField(null=True)
    hand_wash = models.TextField(null=True)

    # person case properties
    name = models.TextField(null=True)
    dob = models.DateField(null=True)
    sex = models.TextField(null=True)
    migration_status = models.TextField(null=True)
    has_aadhar_number = models.NullBooleanField()
    contact_phone_number = models.TextField(null=True)

    # household properties
    hh_address = models.TextField(null=True)
    hh_religion = models.TextField(null=True)
    hh_caste = models.TextField(null=True)
    hh_bpl_apl = models.TextField(null=True)

    # delivery form
    child_cried = models.TextField(null=True)
    ccs_record_case_id = models.TextField(null=True)

    @classmethod
    def agg_from_child_health_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-child_health_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{child_tablename}" AS child (
            domain, person_case_id, child_health_case_id, mother_case_id, opened_on, closed_on,
            birth_weight, breastfed_within_first, is_exclusive_breastfeeding, comp_feeding,
            diet_diversity, diet_quantity, hand_wash
        ) (
            SELECT
                %(domain)s AS domain,
                person_case_id, doc_id, mother_case_id, opened_on, closed_on,
                birth_weight, breastfed_within_first, is_exclusive_breastfeeding, comp_feeding,
                diet_diversity, diet_quantity, hand_wash
            FROM "{child_health_cases_ucr_tablename}" child_health
        )
        ON CONFLICT (child_health_case_id) DO UPDATE SET
           mother_case_id = EXCLUDED.mother_case_id,
           closed_on = EXCLUDED.closed_on,
           birth_weight = EXCLUDED.birth_weight,
           breastfed_within_first = EXCLUDED.breastfed_within_first,
           is_exclusive_breastfeeding = EXCLUDED.is_exclusive_breastfeeding,
           comp_feeding = EXCLUDED.comp_feeding,
           diet_diversity = EXCLUDED.diet_diversity,
           diet_quantity = EXCLUDED.diet_quantity,
           hand_wash = EXCLUDED.hand_wash
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
            migration_status = person.migration_status,
            has_aadhar_number = person.has_aadhar_number,
            contact_phone_number = person.contact_phone_number
        FROM (
            SELECT
                household_case_id,
                doc_id,
                dob,
                sex,
                migration_status,
                aadhar_number IS NOT NULL and aadhar_number != '' AS has_aadhar_number,
                contact_phone_number
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
            village_id = household.village_owner_id,
            hh_address = household.hh_address,
            hh_religion = household.hh_religion,
            hh_caste = household.hh_caste,
            hh_bpl_apl = household.hh_bpl_apl
        FROM (
            SELECT
                doc_id,
                awc_owner_id,
                village_owner_id,
                hh_address,
                hh_religion,
                hh_caste,
                hh_bpl_apl
            FROM "{household_cases_ucr_tablename}"
        ) household
        WHERE child.household_case_id = household.doc_id
        """.format(
            child_tablename=cls._meta.db_table,
            household_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_tasks_case_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-child_tasks_cases')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            tasks_case_id = tasks.doc_id
        FROM (
            SELECT doc_id, child_health_case_id
            FROM "{tasks_cases_ucr_tablename}"
        ) tasks
        WHERE child.child_health_case_id = tasks.child_health_case_id
        """.format(
            child_tablename=cls._meta.db_table,
            tasks_cases_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_delivery_forms_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-delivery_forms')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        UPDATE "{child_tablename}" AS child SET
            ccs_record_case_id = delivery_forms.ccs_record_case_id,
            child_cried = delivery_forms.child_cried
        FROM (
            SELECT child_health_case_id,
                   LAST_VALUE(ccs_record_case_id) OVER w AS ccs_record_case_id,
                   LAST_VALUE(child_cried) OVER w as child_cried
            FROM "{delivery_form_ucr_tablename}"
            WINDOW w AS (PARTITION BY child_health_case_id ORDER BY timeend DESC)
        ) AS delivery_forms
        WHERE child.child_health_case_id = delivery_forms.child_health_case_id
        """.format(
            child_tablename=cls._meta.db_table,
            delivery_form_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classproperty
    def aggregation_queries(self):
        return [
            self.agg_from_child_health_case_ucr,
            self.agg_from_person_case_ucr,
            self.agg_from_household_case_ucr,
            self.agg_from_tasks_case_ucr,
            self.agg_from_village_ucr,
            self.agg_from_awc_ucr,
            self.agg_from_delivery_forms_ucr,
        ]


class ChildHistory(models.Model):
    """The history of form properties for any child registered."""

    child_health_case_id = models.TextField(primary_key=True)

    weight_child_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    height_child_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    zscore_grading_wfa_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    zscore_grading_hfa_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)
    zscore_grading_wfh_history = ArrayField(ArrayField(models.TextField(), size=2), null=True)

    @classmethod
    def agg_from_growth_monitoring_forms_ucr(cls, domain, window_start, window_end):
        doc_id = StaticDataSourceConfiguration.get_doc_id(domain, 'reach-growth_monitoring_forms')
        config, _ = get_datasource_config(doc_id, domain)
        ucr_tablename = get_table_name(domain, config.table_id)

        return """
        INSERT INTO "{child_history_tablename}" AS child (
            child_health_case_id, weight_child_history, height_child_history, zscore_grading_wfa_history,
            zscore_grading_hfa_history, zscore_grading_wfh_history
        ) (
            SELECT child_health_case_id,
                   array_agg(weight_child) AS weight_child_history,
                   array_agg(height_child) AS height_child_history,
                   array_agg(zscore_grading_wfh) AS zscore_grading_wfh_history,
                   array_agg(zscore_grading_hfa) AS zscore_grading_hfa_history,
                   array_agg(zscore_grading_wfa) AS zscore_grading_wfa_history
            FROM (
                SELECT child_health_case_id,
                       ARRAY[timeend::text, weight_child] AS weight_child,
                       ARRAY[timeend::text, height_child] AS height_child,
                       ARRAY[timeend::text, zscore_grading_wfh] AS zscore_grading_wfh,
                       ARRAY[timeend::text, zscore_grading_hfa] AS zscore_grading_hfa,
                       ARRAY[timeend::text, zscore_grading_wfa] AS zscore_grading_wfa
                FROM "{growth_monitoring_ucr_tablename}"
            ) growth_monitoring
            GROUP BY person_case_id
        )
        ON CONFLICT (child_health_case_id) DO UPDATE SET
           weight_child_history = EXCLUDED.weight_child_history,
           height_child_history = EXCLUDED.height_child_history,
           zscore_grading_wfh_history = EXCLUDED.zscore_grading_wfh_history,
           zscore_grading_hfa_history = EXCLUDED.zscore_grading_hfa_history,
           zscore_grading_wfa_history = EXCLUDED.zscore_grading_wfa_history
        """.format(
            child_history_tablename=cls._meta.db_table,
            growth_monitoring_ucr_tablename=ucr_tablename,
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classproperty
    def aggregation_queries(cls):
        return [
            cls.agg_from_growth_monitoring_forms_ucr,
        ]


class AggLocation(models.Model):
    """Abstract base model for aggregate location tables.

    Child classes should define location_levels and fields for each level.
    """

    domain = models.TextField()

    month = models.DateField()

    registered_eligible_couples = models.PositiveIntegerField(null=True)
    registered_pregnancies = models.PositiveIntegerField(null=True)
    registered_children = models.PositiveIntegerField(null=True)

    eligible_couples_using_fp_method = models.PositiveIntegerField(null=True)
    high_risk_pregnancies = models.PositiveIntegerField(null=True)
    institutional_deliveries = models.PositiveIntegerField(null=True)
    total_deliveries = models.PositiveIntegerField(null=True)

    @classmethod
    def agg_from_woman_table(cls, domain, window_start, window_end):
        base_tablename = Woman._meta.db_table

        return """
        INSERT INTO "{agg_tablename}" AS agg (
            domain, {location_levels}, month,
            registered_eligible_couples,
            registered_pregnancies,
            eligible_couples_using_fp_method
        ) (
            SELECT
                %(domain)s, {select_location_levels}, %(window_start)s AS month,
                COALESCE(COUNT(*) FILTER (WHERE
                    (NOT daterange(%(window_start)s, %(window_end)s) && any(pregnant_ranges) OR pregnant_ranges IS NULL)
                    AND migration_status IS DISTINCT FROM 'migrated'
                    AND marital_status = 'married'
                ), 0) as registered_eligible_couples,
                COALESCE(COUNT(*) FILTER (WHERE
                    daterange(%(window_start)s, %(window_end)s) && any(pregnant_ranges)
                    AND migration_status IS DISTINCT FROM 'migrated'
                ), 0) as registered_pregnancies,
                COALESCE(COUNT(*) FILTER (WHERE
                    daterange(%(window_start)s, %(window_end)s) && any(fp_current_method_ranges)
                    AND migration_status IS DISTINCT FROM 'migrated'
                ), 0) as eligible_couples_using_fp_method
            FROM "{woman_tablename}" woman
            WHERE daterange(opened_on, closed_on) && daterange(%(window_start)s, %(window_end)s)
                  AND (opened_on < closed_on OR closed_on IS NULL)
                  AND state_id IS NOT NULL
            GROUP BY ROLLUP ({location_levels})
        )
        ON CONFLICT ({location_levels}, month) DO UPDATE SET
           registered_eligible_couples = EXCLUDED.registered_eligible_couples,
           registered_pregnancies = EXCLUDED.registered_pregnancies,
           eligible_couples_using_fp_method = EXCLUDED.eligible_couples_using_fp_method
        """.format(
            agg_tablename=cls._meta.db_table,
            woman_tablename=base_tablename,
            select_location_levels=', '.join("COALESCE({}, 'ALL')".format(lvl) for lvl in cls.location_levels),
            location_levels=', '.join(cls.location_levels),
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_ccs_record_table(cls, domain, window_start, window_end):
        base_tablename = CcsRecord._meta.db_table

        return """
        INSERT INTO "{agg_tablename}" AS agg (
            domain, {location_levels}, month,
            high_risk_pregnancies,
            institutional_deliveries,
            total_deliveries
        ) (
            SELECT
                %(domain)s, {select_location_levels}, %(window_start)s AS month,
                COALESCE(COUNT(*) FILTER (WHERE hrp = 'yes'), 0) as high_risk_pregnancies,
                COALESCE(COUNT(*) FILTER (WHERE
                    add <@ daterange(%(window_start)s, %(window_end)s)
                    AND child_birth_location = 'hospital'
                ), 0) as institutional_deliveries,
                COALESCE(COUNT(*) FILTER (WHERE
                    add <@ daterange(%(window_start)s, %(window_end)s)
                ), 0) as total_deliveries
            FROM "{woman_tablename}" woman
            WHERE daterange(opened_on, closed_on) && daterange(%(window_start)s, %(window_end)s)
                  AND daterange(opened_on, add) && daterange(%(window_start)s, %(window_end)s)
                  AND (opened_on < closed_on OR closed_on IS NULL)
                  AND state_id IS NOT NULL
            GROUP BY ROLLUP({location_levels})
        )
        ON CONFLICT ({location_levels}, month) DO UPDATE SET
           high_risk_pregnancies = EXCLUDED.high_risk_pregnancies,
           institutional_deliveries = EXCLUDED.institutional_deliveries,
           total_deliveries = EXCLUDED.total_deliveries
        """.format(
            agg_tablename=cls._meta.db_table,
            woman_tablename=base_tablename,
            select_location_levels=', '.join("COALESCE({}, 'ALL')".format(lvl) for lvl in cls.location_levels),
            location_levels=', '.join(cls.location_levels),
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    @classmethod
    def agg_from_child_table(cls, domain, window_start, window_end):
        base_tablename = Child._meta.db_table

        return """
        INSERT INTO "{agg_tablename}" AS agg (
            domain, {location_levels}, month,
            registered_children
        ) (
            SELECT
                %(domain)s,
                {select_location_levels},
                %(window_start)s AS month,
                COALESCE(COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM age(%(window_end)s, dob)) < 5), 0) as registered_children
            FROM "{child_tablename}" child
            WHERE daterange(opened_on, closed_on) && daterange(%(window_start)s, %(window_end)s)
                  AND (opened_on < closed_on OR closed_on IS NULL)
                  AND state_id IS NOT NULL
            GROUP BY ROLLUP({location_levels})
        )
        ON CONFLICT ({location_levels}, month) DO UPDATE SET
           registered_children = EXCLUDED.registered_children
        """.format(
            agg_tablename=cls._meta.db_table,
            child_tablename=base_tablename,
            select_location_levels=', '.join("COALESCE({}, 'ALL')".format(lvl) for lvl in cls.location_levels),
            location_levels=', '.join(cls.location_levels),
        ), {'domain': domain, 'window_start': window_start, 'window_end': window_end}

    class Meta(object):
        abstract = True


class AggAwc(AggLocation):
    location_levels = ['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']

    state_id = models.TextField()
    district_id = models.TextField()
    block_id = models.TextField()
    supervisor_id = models.TextField()
    awc_id = models.TextField()

    @classproperty
    def aggregation_queries(self):
        return [
            self.agg_from_woman_table,
            self.agg_from_ccs_record_table,
            self.agg_from_child_table,
        ]

    class Meta(object):
        unique_together = (
            ('state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id', 'month'),
        )


class AggVillage(AggLocation):
    location_levels = ['state_id', 'district_id', 'taluka_id', 'phc_id', 'sc_id', 'village_id']

    state_id = models.TextField()
    district_id = models.TextField()
    taluka_id = models.TextField()
    phc_id = models.TextField()
    sc_id = models.TextField()
    village_id = models.TextField()

    @classproperty
    def aggregation_queries(self):
        return [
            self.agg_from_woman_table,
            self.agg_from_ccs_record_table,
            self.agg_from_child_table,
        ]

    class Meta(object):
        unique_together = (
            ('state_id', 'district_id', 'taluka_id', 'phc_id', 'sc_id', 'village_id', 'month'),
        )


class AggregationInformation(models.Model):
    """Used to track the performance and timings of our data aggregations"""

    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    end_time = models.DateTimeField(null=True, help_text="Time the aggregation completed")

    domain = models.TextField()
    step = models.TextField(help_text="Slug for the step of the aggregation")
    aggregation_window_start = models.DateTimeField()
    aggregation_window_end = models.DateTimeField()
