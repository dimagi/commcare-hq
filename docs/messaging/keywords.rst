Keywords
========

A Keyword (SurveyKeyword, corehq.apps.sms.reminders.models) defines an action or set of actions to be taken
when an inbound SMS is received whose first word matches the keyword configuration.

Any number of actions can be taken, which include:

* Replying with an SMS or SMS Survey
* Sending an SMS or SMS Survey to another contact or group of contacts
* Processing the SMS as a Structured SMS

Keywords tie into the Inbound SMS framework through the keyword handler
(corehq.apps.sms.handlers.keyword.sms_keyword_handler, see settings.SMS_HANDLERS), and use the Reminders
framework to carry out their action(s).

Behind the scenes, all actions besides processing Structured SMS create a reminder definition to be sent
immediately. So any functionality provided by a reminder definition can be added to be supported as an
Keyword action.
