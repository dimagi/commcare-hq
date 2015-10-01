from dimagi.ext.couchdbkit import *
from corehq.apps.app_manager.exceptions import ScheduleError
from corehq.apps.app_manager.models.common import (
    FormActionCondition,
    FormIdProperty,
    IndexedSchema,
)


class ScheduleVisit(IndexedSchema):
    """
    due:         Days after the anchor date that this visit is due
    starts:      Days before the due date that this visit is valid from
    expires:     Days after the due date that this visit is valid until (optional)

    repeats:     Whether this is a repeat visit (one per form allowed)
    increment:   Days after the last visit that the repeat visit occurs
    """
    due = IntegerProperty()
    starts = IntegerProperty()
    expires = IntegerProperty()
    repeats = BooleanProperty(default=False)
    increment = IntegerProperty()

    @property
    def id(self):
        """Visits are 1-based indexed"""
        _id = super(ScheduleVisit, self).id
        return _id + 1


class FormSchedule(DocumentSchema):
    """
    starts:                     Days after the anchor date that this schedule starts
    expires:                    Days after the anchor date that this schedule expires (optional)
    visits:		        List of visits in this schedule
    allow_unscheduled:          Allow unscheduled visits in this schedule
    transition_condition:       Condition under which we transition to the next phase
    termination_condition:      Condition under which we terminate the whole schedule
    """
    enabled = BooleanProperty(default=True)

    starts = IntegerProperty()
    expires = IntegerProperty()
    allow_unscheduled = BooleanProperty(default=False)
    visits = SchemaListProperty(ScheduleVisit)
    get_visits = IndexedSchema.Getter('visits')

    transition_condition = SchemaProperty(FormActionCondition)
    termination_condition = SchemaProperty(FormActionCondition)


class SchedulePhaseForm(IndexedSchema):
    """
    A reference to a form in a schedule phase.
    """
    form_id = FormIdProperty("modules[*].schedule_phases[*].forms[*].form_id")


class SchedulePhase(IndexedSchema):
    """
    SchedulePhases are attached to a module.
    A Schedule Phase is a grouping of forms that occur within a period and share an anchor
    A module should not have more than one SchedulePhase with the same anchor

    anchor:                     Case property containing a date after which this phase becomes active
    forms: 			The forms that are to be filled out within this phase
    """
    anchor = StringProperty()
    forms = SchemaListProperty(SchedulePhaseForm)

    @property
    def id(self):
        """ A Schedule Phase is 1-indexed """
        _id = super(SchedulePhase, self).id
        return _id + 1

    @property
    def phase_id(self):
        return "{}_{}".format(self.anchor, self.id)

    def get_module(self):
        return self._parent

    _get_forms = IndexedSchema.Getter('forms')

    def get_forms(self):
        """Returns the actual form objects related to this phase"""
        module = self.get_module()
        return (module.get_form_by_unique_id(form.form_id) for form in self._get_forms())

    def get_form(self, desired_form):
        return next((form for form in self.get_forms() if form.unique_id == desired_form.unique_id), None)

    def get_phase_form_index(self, form):
        """
        Returns the index of the form with respect to the phase

        schedule_phase.forms = [a,b,c]
        schedule_phase.get_phase_form_index(b)
        => 1
        schedule_phase.get_phase_form_index(c)
        => 2
        """
        return next((phase_form.id for phase_form in self._get_forms() if phase_form.form_id == form.unique_id),
                    None)

    def remove_form(self, form):
        """Remove a form from the phase"""
        idx = self.get_phase_form_index(form)
        if idx is None:
            raise ScheduleError("That form doesn't exist in the phase")

        self.forms.remove(self.forms[idx])

    def add_form(self, form):
        """Adds a form to this phase, removing it from other phases"""
        old_phase = form.get_phase()
        if old_phase is not None and old_phase.anchor != self.anchor:
            old_phase.remove_form(form)

        if self.get_form(form) is None:
            self.forms.append(SchedulePhaseForm(form_id=form.unique_id))

    def change_anchor(self, new_anchor):
        if new_anchor is None or new_anchor.strip() == '':
            raise ScheduleError(_("You can't create a phase without an anchor property"))

        self.anchor = new_anchor

        if self.get_module().phase_anchors.count(new_anchor) > 1:
            raise ScheduleError(_("You can't have more than one phase with the anchor {}").format(new_anchor))
