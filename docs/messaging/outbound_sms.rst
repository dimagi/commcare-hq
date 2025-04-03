Outbound SMS
============

The SMS framework uses a queuing architecture to make it easier to scale SMS processing power horizontally.

The process to send an SMS from within the code is as follows. The only step you need to do is the first, and
the rest happen automatically.

#. Invoke one of the send_* functions found in `corehq.apps.sms.api <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/api.py>`_:
    send_sms
        used to send SMS to a one-way phone number represented as a string
    send_message_to_verified_number
        use to send SMS or connect message to a two-way phone number represented as a PhoneNumber object.
        This function is also used to send a connect message if the two way number is a
        ConnectMessagingNumber object, but those are process directly by the
        `ConnectID messaging backend <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/smsbackends/connectid/backend.py>`_
        and do not follow the rest of the processing described in this documentation
    send_sms_with_backend
        used to send SMS with a specific SMS backend
    send_sms_with_backend_name
        used to send SMS with the given SMS backend name which will be resolved to an SMS backend

#. The framework creates a `corehq.apps.sms.models.QueuedSMS <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
   object representing the SMS to be sent.

#. The SMS Queue polling process (python manage.py run_sms_queue), which runs as a supervisor process on one of
   the celery machines, picks up the QueuedSMS object and passes it to `corehq.apps.sms.tasks.process_sms <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/tasks.py>`_.

#. process_sms attempts to send the SMS. If an error happens, it is retried up to 2 more times on 5 minute
   intervals. After 3 total attempts, any failure causes the SMS to be marked with error = True.

#. Whether the SMS was processed successfully or not, the QueuedSMS object is deleted and replaced by an identical
   looking `corehq.apps.sms.models.SMS <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
   object for reporting.

At a deeper level, process_sms performs the following important functions for outbound SMS.  To find out other
more detailed functionality provided by process_sms, see the code.

#. If the domain has restricted the times at which SMS can be sent, check those and requeue the SMS if it
   is not currently an allowed time.

#. Select an SMS backend by looking in the following order:
    * If using a two-way phone number, look up the SMS backend with the name given in the backend_id property
    * If the domain has a default SMS backend specified, use it
    * Look up an appropriate global SMS backend by checking the phone number's prefix against the global
      SQLMobileBackendMapping entries
    * Use the catch-all global backend (found from the global SQLMobileBackendMapping entry with prefix = '*')

#. If the SMS backend has configured rate limiting or load balancing across multiple numbers, enforce those
   constraints.

#. Pass the SMS to the send() method of the SMS Backend, which is an instance of
   `corehq.apps.sms.models.SQLSMSBackend <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_.
