Monitoring Email Events with Amazon SES
==============================================

If you are using Amazon SES as your email provider (through SMTP), you can monitor what happens to emails sent through commcare's messaging features (broadcasts, reminders, etc).

We use Amazon's Simple Notification System to send callbacks to the `/log_email_event` endpoint.

1. Add SES_CONFIGURATION_SET to localsettings. Call this something memorable e.g. `production-email-events`. You'll use this name later. Deploy localsettings, and restart services (this needs to be done before the next steps).
2. Create an SNS Topic here https://console.aws.amazon.com/sns/v3/home?region=us-east-1#/topics .
3. Add a subscription which points to `https://{HQ_ADDRESS}/log_email_event/`. It should automatically get confirmed.
4. Create an SES Configuration Set, with the name you created in step 1.
5. Add the SNS topic you created in step 2 as the desination for this configuration step. Select the event types you want - we currently support `Send`, `Delivery`, and `Bounce`.
6. Messages you send with the X-COMMCAREHQ-MESSAGE-ID and X-SES-CONFIGURATION-SET headers should now receive notification updates. The X-COMMCAREHQ-MESSAGE-ID headers should include the ID of a MessagingSubEvent.
