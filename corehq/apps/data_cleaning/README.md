# Data Cleaning on CommCare HQ

## Case Bulk Data Editing Feature

### Overview

The bulk data editing feature currently supports bulk edits on cases. To orient yourself with this feature,
please visit `views/main.py` as the starting point for exploring code.

This feature makes use of `HTMX` with `HqHtmxActionMixin` defining the different endpoints for a view,
`alpine.js` for light client-side interactivity, and `django-tables` to render the tabular view.

NOTE: make sure the `domain` you are using is on `Advanced` or above edition.

### Generating Data

When trying this out locally, it helps to have case data available with simulated data cleaning "issues".

The generated data will:
- simulate free-input issues (capitalization, whitespace, missing values) for: `nickname`, `description`, and `plant_name` (`plant_name` won't be missing, however)
- missing values for: `num_leaves`. `health_indicators`, `pot_type`, `health_indicators`
- renamed properties: `height_cm` -> `height`

The above case properties also vary across data types, which will be helpful for when we add type-protection to
inputs, or for when we want to use the forms in the future bulk edit forms tool.

Below are three management commands that:

- create an application with a `plant` case
- generate mobile users who will be submitting forms to update the `plant` case
- submit forms with simulated data cleaning issues using the generated mobile users above

#### 1. Create the test application "Plant Care"

First, you need to create the "Plant Care" app the `domain` you want to test bulk data editing with:

```bash
./manage.py dc_create_test_app <domain>
```

#### 2. Create Test Mobile Users

Once the app is installed in the above `domain`, you can run the next management command to generate
mobile users that will be submitting forms to this app. Please specify a secure `user_password` as well as
the `num_users` you would like to generate.

```bash
./manage.py dc_create_test_users <domain> <user_password> <num_users>
```

#### 3. Submit Data with Test Mobile Users

This management command utilizes the same approach as the login as functionality in webapps, which is why
you need to specify the `submitting_web_user` (for the audit trail).

There is no need to specify mobile users, as this management command will randomly select from the list of
mobile users created previously.

```bash
./manage.py dc_create_test_data <domain> <submitting_web_user> <num_submissions>
```


#### (Local, OSX) Manually reindex ptop

If you are on OSX (or perhaps you don't have `run_ptop` running), you need to re-index elasticsearch to make that
newly-submitted data visible.

To do this, run:
```bash
./manage.py ptop_preindex --reset
./manage.py ptop_reindexer_v2 sql-form --reset
./manage.py ptop_reindexer_v2 sql-case --reset
```

Now you can navigate to the "Bulk Edit Case Data" tool in the "Data" tab and select the `plant` case for starting a new session.

If you want the renamed property `height_cm` to show up in the case property options, you will need to add it to the Data Dictionary manually.
Once that's added, you will see both `height` and `height_cm` in the column and filter case property options. You will see that where `height` is blank,
`height_cm` will have a value (simulating a renamed property.)
