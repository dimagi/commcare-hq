Reminders
=========

The Reminders framework uses a queuing architecture similar to the SMS framework, to make it easier to scale
reminders processing power horizontally.

To see how this works, we first have to see how the reminders models are setup.

Reminder Definition
^^^^^^^^^^^^^^^^^^^

A reminder definition, represented by a `corehq.apps.reminders.models.CaseReminderHandler <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/models.py>`_
object, defines the rules for:

* what criteria cause a reminder to be triggered
* when the reminder should start once the criteria are fulfilled
* who the reminder should go to
* on what schedule and frequency the reminder should continue to be sent
* the content to send
* what causes the reminder to stop

Reminder Instance
^^^^^^^^^^^^^^^^^

A reminder instance, represented by a `corehq.apps.reminders.models.CaseReminder <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/models.py>`_,
defines an instance of a reminder definition and keeps track of the state of the reminder instance throughout its lifetime.

For example, a reminder definition may define a rule for sending an SMS to a case of type patient, and
sending an SMS appointment reminder to the case 2 days before the case's appointment_date case property.

As soon as a case is created or updated in the given project to meet the criteria of having type patient
and having an appointment_date, the framework will create a reminder instance to track it.
After the reminder is sent 2 days before the appointment_date, the reminder instance is deactivated
to denote that it has completed the defined schedule and should not be sent again.

In order to keep reminder instances responsive to case changes, every time a case is saved, a
`corehq.apps.reminders.tasks.case_changed <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/tasks.py>`_
task is spawned to handle any changes. Similarly, any time a reminder definition is updated, a
`corehq.apps.reminders.tasks.process_reminder_rule <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/tasks.py>`_
task is spawned to rerun it against all cases in the project.

The aim of the framework is to always be completely responsive to all changes. So in the example above,
if a case's appointment_date changes before the appointment reminder is actually sent, the framework will
update the reminder instance automatically in order to reflect the new appointment date. And if the
appointment reminder went out months ago but a new appointment_date value is given to the case for a new
appointment, the same reminder instance is updated again to reflect a new reminder that must go out.

Similarly, if the reminder definition is updated to use a different case property other than appointment_date,
all existing reminder instances are deleted and any new ones are created if they meet the criteria.

Queueing
^^^^^^^^

All of the reminder instances in the database represent the queue of reminders that should be sent.
The way a reminder is processed is as follows:

#. The reminder polling process (python manage.py run_reminder_queue), which runs as a supervisor process on
   one of the celery machines, constantly polls for reminders that should be processed by querying for reminder
   instances that have a next_fire property that is in the past.

#. Once a reminder that needs to be processed has been identified, the framework spawns a
   `corehq.apps.reminders.tasks.fire_reminder <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/tasks.py>`_
   task to handle it.

#. fire_reminder looks up the reminder definition that spawned the reminder instance, and instructs it to 1)
   take the appropriate action that has been configured (for example, send an sms), and 2) update the state of the
   reminder instance so that it gets scheduled for the next action it must take based on the reminder definition.

Event Handlers
^^^^^^^^^^^^^^

A reminder definition sends content of one type. At the time of writing, the content a reminder definition can
be configured to send includes:

* SMS
* SMS Survey
* Outbound IVR Session
* Emails

In the case of SMS Surveys or IVR Sessions, the survey content is defined using a form in an app which is then
played to the recipients over SMS or IVR using touchforms (see `corehq.apps.smsforms <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/smsforms>`_
for this interface with touchforms).

New event handlers can be written and added to the current ones in
`corehq.apps.reminders.event_handlers <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/event_handlers.py>`_, and
each event handler is tied to a reminder definition through the reminder definition's method attribute and
the `corehq.apps.reminders.event_handlers.EVENT_HANDLER_MAP <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/reminders/event_handlers.py>`_.
