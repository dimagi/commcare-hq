from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.suite_xml.basic import SuiteContributor
from corehq.apps.app_manager.suite_xml.xml import Schedule, ScheduleFixture, ScheduleVisit


class SchedulerContributor(SuiteContributor):
    section = 'fixtures'
    
    def contribute(self):
        self.suite.fixtures.extend(self.fixtures)

    @property
    def fixtures(self):
        schedule_modules = (module for module in self.modules if getattr(module, 'has_schedule', False) and
                            module.all_forms_require_a_case)
        schedule_forms = (form for module in schedule_modules for form in module.get_forms())
        for form in schedule_forms:
            schedule = form.schedule
            fx = ScheduleFixture(
                id=id_strings.schedule_fixture(form),
                schedule=Schedule(
                    expires=schedule.expires,
                    post_schedule_increment=schedule.post_schedule_increment
                ))
            for i, visit in enumerate(schedule.visits):
                fx.schedule.visits.append(ScheduleVisit(
                    id=i + 1,
                    due=visit.due,
                    late_window=visit.late_window
                ))

            yield fx
