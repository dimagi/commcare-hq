## Analytics
We use multiple Analytics platforms. Google Analytics and Kissmetrics calls are done mainly using respective Javascript APIs. We track few aggregated user properties on [Kissmetrics from server side](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py#L210). For Hubspot we use their REST API from server side as well.

[Directory of events and properties we track in these platforms](https://docs.google.com/spreadsheets/d/1frMdFeznNcMAIyMW3pG3zes6mmY03UG67HyMUHXlb-s/edit#gid=1804103672)

### Google Analytics and Kissmetrics JS
See [analytics_all.html](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/hqwebapp/templates/hqwebapp/includes/analytics_all.html) and see example usages

### Server Side Kissmetrics
All kissmetrics actions can be done server side instead of client side using the `track_workflow` and `identify` functions in the [analytics tasks](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py) file. `track_workflow` is used to register events and accepts an optional argument to update properties as well. `identify` can be used if you are only looking to update a property.
### Hubspot

#### Adding/Removing Hubspot properties

We track various user properties as [Hubspot Contact Properties](http://knowledge.hubspot.com/contacts-user-guide-v2/how-to-use-contact-and-company-properties). We have bunch of celery tasks and function that update these contact properties via [Hubspot REST API](http://developers.hubspot.com/docs/methods/contacts/create_or_update). We can update only those properties that are available on Hubspot portal. When we mention new Hubspot properties in HQ-Hubspot API calls, make sure that these properties are available in Hubspot portal. If they are not available, [create](http://knowledge.hubspot.com/contacts-user-guide-v2/how-to-create-contact-and-company-properties) them or ping marketing team to have them created on Hubspot portal first. To update a list of properties you can use the [update_hubspot_properties](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py#L174) function.

#### Hubspot Form Submissions
We use the hubspot form API to submit forms to hubspot via the `_send_form_to_hubspot` function in the analytics tasks file. You can look through that file for examples but the general procedure is to create a new function with the `@analytics_task()` decorator to make it asynchronous and ensure it is retried on failure. This function should then call `_send_form_to_hubspot` with the form id of the form you are trying to submit. All form ids are listed as constants at the top of the file, and new forms can be created on the hubspot site.

#### Signup Related Hubspot Analytics
Much of the analytics we use in hubspot are generated during the signup process. We send down those analytics in the `track_user_sign_in_on_hubspot` [function](https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/analytics/tasks.py#L181). Both a dictionary or properties, and a special signup form are sent down then and if changes need to be made to sign up analytics, they should be made there.

#### Testing

To start testing, run Celery and update `HUBSPOT_API_KEY` and `HUBSPOT_ID` in `settings.ANALYTICS_IDS`. Hubspot provides a public demo portal with API access for testing. The credentials for this are available on their [API overview page](http://developers.hubspot.com/docs/overview). If you need to test using our production portal the credentials can be found in dimagi_shared keepass. Let marketing know before testing on production portal and clean-up after the testing is finished
