from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.const import (
    SCHEDULE_DATE_CASE_OPENED, SCHEDULE_LAST_VISIT, SCHEDULE_LAST_VISIT_DATE,
    SCHEDULE_GLOBAL_NEXT_VISIT_DATE, SCHEDULE_NEXT_DUE
)
from corehq.apps.app_manager.exceptions import ScheduleError
from corehq.apps.app_manager.suite_xml.const import FIELD_TYPE_SCHEDULE
from corehq.apps.app_manager.suite_xml.contributors import SectionContributor
from corehq.apps.app_manager.suite_xml.xml_models import (
    DetailVariable, ScheduleFixtureVisit,
    ScheduleFixture, Schedule
)
from corehq.apps.app_manager.templatetags.xforms_extras import trans
from corehq.apps.app_manager.xpath import ScheduleFormXPath


class SchedulerFixtureContributor(SectionContributor):
    section_name = 'fixtures'

    def get_section_elements(self):
        schedule_modules = (module for module in self.modules
                            if getattr(module, 'has_schedule', False) and module.all_forms_require_a_case)
        schedule_phases = (phase for module in schedule_modules for phase in module.get_schedule_phases())
        schedule_forms = (form for phase in schedule_phases for form in phase.get_forms())

        for form in schedule_forms:
            schedule = form.schedule

            if schedule is None:
                raise ScheduleError(_("There is no schedule for form {form_id}").format(form_id=form.unique_id))

            visits = [ScheduleFixtureVisit(id=visit.id,
                                           due=visit.due,
                                           starts=visit.starts,
                                           expires=visit.expires,
                                           repeats=visit.repeats,
                                           increment=visit.increment)
                      for visit in schedule.get_visits()]

            schedule_fixture = ScheduleFixture(
                id=id_strings.schedule_fixture(form.get_module(), form.get_phase(), form),
                schedule=Schedule(
                    starts=schedule.starts,
                    expires=schedule.expires if schedule.expires else '',
                    allow_unscheduled=schedule.allow_unscheduled,
                    visits=visits,
                )
            )
            yield schedule_fixture


def schedule_detail_variables(module, detail, detail_column_infos):
    has_schedule_columns = any(ci.column.field_type == FIELD_TYPE_SCHEDULE for ci in detail_column_infos)
    has_schedule = getattr(module, 'has_schedule', False)
    if (has_schedule and module.all_forms_require_a_case() and has_schedule_columns):
        yield DetailVariable(name=SCHEDULE_DATE_CASE_OPENED, function="date_opened")  # date case is opened
        forms_due = []
        last_visit_dates = []
        for phase in module.get_schedule_phases():
            if not phase.anchor:
                raise ScheduleError(_("Schedule Phase in module '{module_name}' is missing an anchor")
                                    .format(module_name=module.default_name()))

            for form in phase.get_forms():
                """
                Adds the following variables for each form:
                <anchor_{form_id} function="{anchor}"/>
                <last_visit_number_{form_id} function="{last_visit_number}"/>
                <last_visit_date_{form_id} function="{last_visit_date}"/>
                <next_{form_id} function={phase_set}/>
                """
                if not form.schedule_form_id:
                    raise ScheduleError(
                        _("'{form_name}' in '{module_name}' is missing an abbreviation")
                        .format(form_name=trans(form["name"], langs=[module.get_app().default_language]),
                                module_name=module.default_name()))
                form_xpath = ScheduleFormXPath(form, phase, module)
                name = "next_{}".format(form.schedule_form_id)
                forms_due.append("${}".format(name))

                # Add an anchor and last_visit variables so we can reference it in the calculation
                yield DetailVariable(name=form_xpath.anchor_detail_variable_name, function=phase.anchor)
                yield DetailVariable(name=form_xpath.last_visit_detail_variable_name,
                                     function=SCHEDULE_LAST_VISIT.format(form.schedule_form_id))
                yield DetailVariable(name=form_xpath.last_visit_date_detail_variable_name,
                                     function=SCHEDULE_LAST_VISIT_DATE.format(form.schedule_form_id))
                last_visit_dates.append(form_xpath.last_visit_date_detail_variable_name)
                if phase.id == 1:
                    # If this is the first phase, `current_schedule_phase` and
                    # last_visit_num might not be set yet
                    yield DetailVariable(name=name, function=form_xpath.first_visit_phase_set)
                else:
                    yield DetailVariable(name=name, function=form_xpath.xpath_phase_set)

        yield DetailVariable(name=SCHEDULE_GLOBAL_NEXT_VISIT_DATE,
                             function='date(min({}))'.format(','.join(forms_due)))
        yield DetailVariable(name=SCHEDULE_NEXT_DUE,
                             function=ScheduleFormXPath.next_visit_date(last_visit_dates))
        yield DetailVariable(name='is_late', function='${} < today()'.format(SCHEDULE_NEXT_DUE))

        if len(forms_due) != len(set(forms_due)):
            raise ScheduleError(_("Your app has multiple forms with the same schedule abbreviation"))
