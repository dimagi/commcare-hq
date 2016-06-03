Outbound SMS
============

The SMS framework uses a queuing architecture to make it easier to scale SMS processing power horizontally.

The process to send an SMS from within the code is as follows. The only step you need to do is the first, and
the rest happen automatically.

#. Invoke one of the send_sms* functions found in corehq/apps/sms/api.py:
    send_sms
        used to send SMS to a one-way phone number represented as a string
    send_sms_to_verified_number
        use to send SMS to a two-way phone number represented as a PhoneNumber object
    send_sms_with_backend
        used to send SMS with a specific SMS backend
    send_sms_with_backend_name
        used to send SMS with the given SMS backend name which will be resolved to an SMS backend

#. The framework creates a QueuedSMS object representing the SMS to be sent.

#. The SMS Queue polling process (python manage.py run_sms_queue), which runs as a supervisor process on one of
the celery machines, picks up the QueuedSMS object and passes it to process_sms (corehq/apps/sms/tasks.py).

#. process_sms attempts to send the SMS. If an error happens, it is retried up to 2 more times on 5 minute
intervals. After 3 total attempts, any failure causes the SMS to be marked with error = True.

At a deeper level, process_sms performs the following important functions for outbound SMS.  To find out other
more detailed functionality provided by process_sms, see the code.

#. If the domain has restricted the times at which SMS can be sent, check those and requeue the SMS if it
is not an allowed time.

#. Select an SMS backend by looking in the following order:
    * If using a two-way phone number, look up the SMS backend with the name given in the backend_id property
    * If the domain has a default SMS backend specified, use it
    * Look up an appropriate global SMS backend by checking the phone number's prefix against the global
      SQLMobileBackendMapping entries
    * Use the catch-all global backend (found from the global SQLMobileBackendMapping entry with prefix = '*')

#. If the SMS backend has configured rate limiting or load balancing across multiple numbers, enforce those
constraints.

#. Pass the SMS to the send() method of the SMS Backend, which is an instance of SQLSMSBackend
(corehq/apps/sms/models.py).
