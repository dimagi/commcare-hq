Inbound SMS
===========

Inbound SMS uses the same queueing architecture as outbound SMS does.

The entry point to all inbound SMS is the incoming function (corehq/apps/sms/api.py). All SMS backends
which accept inbound SMS call the incoming function.

From there, the following functions are performed at a high level:

#. The framework creates a QueuedSMS object representing the SMS to be processed.

#. The SMS Queue polling process (python manage.py run_sms_queue), which runs as a supervisor process on one of
the celery machines, picks up the QueuedSMS object and passes it to process_sms (corehq/apps/sms/tasks.py).

#. process_sms attempts to process the SMS. If an error happens, it is retried up to 2 more times on 5 minute
intervals. After 3 total attempts, any failure causes the SMS to be marked with error = True.

At a deeper level, process_sms performs the following important functions for inbound SMS. To find out other
more detailed functionality provided by process_sms, see the code.

#. Look up a two-way phone number for the given phone number string.

#. If a two-way phone number is found, pass the SMS on to each inbound SMS handler
(defined in settings.SMS_HANDLERS) until one of them returns True, at which point processing stops.

#. If a two-way phone number is not found, try to pass the SMS on to the SMS handlers that don't require
two-way phone numbers (the phone verification workflow, self-registration over SMS workflows)
