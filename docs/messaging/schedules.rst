Scheduled Messages
==================

The messaging framework supports scheduling messages to be sent on a one-time or recurring basis.

It uses a queuing architecture similar to the SMS framework, to make it easier to scale
reminders processing power horizontally.

An earlier incarnation of this framework was called "reminders", so some code references to reminders remain, such
as the ``reminder_queue``.

Definitions
^^^^^^^^^^^

Scheduled messages are represented in the UI as "broadcasts" and "conditional alerts."

Broadcasts, represented by the subclasses of `corehq.messaging.scheduling.models.abstract.Broadcast <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/models/abstract.py>`_,
allow configuring a recurring schedule to send a particular message type and content to a particular set of recipients.

Conditional alerts, represented by `corehq.apps.data_interfaces.models.AutomaticUpdateRule <http://github.com/dimagi/commcare-hq/blob/master/corehq/apps/data_interfaces/models.py>`_,
contain a similar recurring schedule but act on cases. They are configured to trigger on when cases meet a set of
criteria, such as a case property changing to a specific value.

The two models share much of their code. This document primarily addresses conditional alerts and will refer to
them as "rules," as most of the code does.

A rule definition, defines the rules for:

* what criteria cause a reminder to be triggered
* when the message should send once the criteria are fulfilled
* who the message should go to
* on what schedule and frequency the message should continue to be sent
* the content to send
* what causes the rule to stop

Conditional Alerts / Case Update Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A conditional alert, represented by `corehq.apps.data_interfaces.models.AutomaticUpdateRule <http://github.com/dimagi/commcare-hq/blob/master/corehq/apps/data_interfaces/models.py>`_,
defines an instance of a rule definition and keeps track of the state of the rule instance throughout its lifetime.

For example, a conditional alert definition may define a rule for sending an SMS to a case of type ``patient``, and
sending an SMS appointment reminder to the case 2 days before the case's ``appointment_date`` case property.

As soon as a case is created or updated in the given project to meet the criteria of having type ``patient``
and having an ``appointment_date``, the framework will create a reminder instance to track it.
After the message is sent 2 days before the ``appointment_date``, the rule instance is deactivated
to denote that it has completed the defined schedule and should not be sent again.

In order to keep messaging responsive to case changes, every time a case is saved, the
`corehq.messaging.tasks.sync_case_for_messaging <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
function is called to handle any changes. This is controlled via `case-pillow`.

Similarly, any time a rule is updated, a
`corehq.messaging.tasks.run_messaging_rule <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
task is spawned to rerun it against all cases in the project.

The aim of the framework is to always be completely responsive to all changes. So in the example above,
if a case's ``appointment_date`` changes before the appointment reminder is actually sent, the framework will
update the schedule instance (more on these below) automatically in order to reflect the new appointment date. And if the
appointment reminder went out months ago but a new ``appointment_date`` value is given to the case for a new
appointment, the same instance is updated again to reflect a new message that must go out.

Similarly, if the rule definition is updated to use a different case property other than ``appointment_date``,
all existing schedule instances are deleted and any new ones are created if they meet the criteria.

Lifecycle of a Rule
^^^^^^^^^^^^^^^^^^^

As mentioned above, whe a rule is changed, all cases of the relevant type in the domain are re-processed.
The steps of this process are as follows:

#. When a conditional alert is created or activated, a
   `corehq.messaging.tasks.initiate_messaging_rule_run <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
   task is spawned.

#. This locks the rule, so that it cannot be edited from the UI, and spawns a
   `corehq.messaging.tasks.run_messaging_rule <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
   task.

#. This task spawns a
   `corehq.messaging.tasks.sync_case_for_messaging_rule <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
   task for every case of the rule's case type. It also adds a
   `corehq.messaging.tasks.set_rule_complete <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/tasks.py>`_
   task to unlock the rule when all of the ``sync_case`` tasks are finished.

#. This task calls `corehq.apps.data_interfaces.models.AutomaticUpdateRule.run_rule
   <https://github.com/dimagi/commcare-hq/blob/7e7c4af896cd0eeeb747bb19cc663741189d23d6/corehq/apps/data_interfaces/models.py#L310>`_
   on its case.

#. ``run_rule`` checks whether or not the case meets the rule's criteria and acts accordingly. When the case
   matches, this calls ``run_actions_when_case_matches`` and then ``when_case_matches``. Conditional alert actions
   use ``CreateScheduleInstanceActionDefinition`` which implements ``when_case_matches`` to call
   `corehq.messaging.scheduling.tasks.refresh_case_alert_schedule_instances <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/tasks.py>`_
   or
   `corehq.messaging.scheduling.tasks.refresh_case_timed_schedule_instances <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/tasks.py>`_
   depending on whether the rule is immediate or scheduled.

#. The refresh functions act on subclasses of
   `corehq.messaging.scheduling.tasks.ScheduleInstanceRefresher <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/tasks.py>`_,
   which create, update, and delete "schedule instance" objects, which are subclasses of
   `corehq.messaging.scheduling.scheduling_partitioned.models.ScheduleInstance <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/scheduling_partitioned/models.py>`_.
   These schedule instances track their schedule, recipients, and state relating to their next event. They are
   processed by a queue (see next section).


Queueing
^^^^^^^^

All of the schedule instances in the database represent the queue of messages that should be sent.
The way a schedule instance is processed is as follows:

#. The polling process (``python manage.py queue_schedule_instances``), which runs as a supervisor process on
   one of the celery machines, constantly polls for schedules that should be processed by querying for schedule
   instances that have a ``next_event_due`` property that is in the past.

#. Once a schedule instance that needs to be processed has been identified, the framework spawns one of several
   tasks from `corehq.messaging.scheduling.tasks <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/scheduling/tasks.py>`_
   to handle it. These tasks include ``handle_alert_schedule_instance``, ``handle_timed_schedule_instance``,
   ``handle_case_alert_schedule_instance``, and ``handle_case_timed_schedule_instance``.

#. The handler looks at the schedule instances and instructs it to 1) take the appropriate action that has been
   configured (for example, send an sms), and 2) update the state of the instance so that it gets scheduled
   for the next action it must take based on the reminder definition. This is handled by
   `corehq.messaging.scheduling.scheduling_partitioned.models.ScheduleInstance.handle_current_event <https://github.com/dimagi/commcare-hq/blob/7e7c4af896cd0eeeb747bb19cc663741189d23d6/corehq/messaging/scheduling/scheduling_partitioned/models.py#L354>`_

A second queue (``python manage.py run_sms_queue``), which is set up similarly on each celery machine that consumes
from the ``reminder_queue``,handles the sending of messages.

Event Handlers
^^^^^^^^^^^^^^

A rule (or broadcast) sends content of one type. At the time of writing, the content a reminder definition can
be configured to send includes:

* SMS
* SMS Survey
* Emails
* Push Notifications

In the case of SMS SurveysSessions, the survey content is defined using a form in an app which is then
played to the recipients over SMS or Whatsapp.
