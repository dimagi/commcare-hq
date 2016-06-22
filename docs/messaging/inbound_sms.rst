Inbound SMS
===========

Inbound SMS uses the same queueing architecture as outbound SMS does.

The entry point to processing an inbound SMS is the `corehq.apps.sms.api.incoming <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/api.py>`_
function. All SMS backends which accept inbound SMS call the incoming function.

From there, the following functions are performed at a high level:

#. The framework creates a `corehq.apps.sms.models.QueuedSMS <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
   object representing the SMS to be processed.

#. The SMS Queue polling process (python manage.py run_sms_queue), which runs as a supervisor process on one of
   the celery machines, picks up the QueuedSMS object and passes it to
   `corehq.apps.sms.tasks.process_sms <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/tasks.py>`_.

#. process_sms attempts to process the SMS. If an error happens, it is retried up to 2 more times on 5 minute
   intervals. After 3 total attempts, any failure causes the SMS to be marked with error = True.

#. Whether the SMS was processed successfully or not, the QueuedSMS object is deleted and replaced by an identical
   looking `corehq.apps.sms.models.SMS <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
   object for reporting.

At a deeper level, process_sms performs the following important functions for inbound SMS. To find out other
more detailed functionality provided by process_sms, see the code.

#. Look up a two-way phone number for the given phone number string.

#. If a two-way phone number is found, pass the SMS on to each inbound SMS handler
   (defined in settings.SMS_HANDLERS) until one of them returns True, at which point processing stops.

#. If a two-way phone number is not found, try to pass the SMS on to the SMS handlers that don't require
   two-way phone numbers (the phone verification workflow, self-registration over SMS workflows)
