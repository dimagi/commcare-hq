How to enable this module
=========================

The ``custom.onse`` module is a custom Django app for the self-hosted
ONSE ISS project.

Follow these steps to enable this module for the ONSE ISS project:

1. In CommCare Cloud, edit the **public.yml** file for your environment.
   You will find an entry named "localsettings" in the file. Inside the
   "localsettings" entry, add a key named "LOCAL_APPS" and set its value
   as follows:

   .. code-block:: yaml

      localsettings:
        LOCAL_APPS:
          - host: "all"
            name: "custom.onse"

2. Deploy the updated configuration to your environment:

   .. code-block:: bash

      $ commcare-cloud <env> update-config


Importing aggregated data from DHIS2
====================================

The ``update_facility_cases_from_dhis2_data_elements()`` task is
*custom* code because it is unusual, in that it imports aggregated data,
and saves it to case properties. One would expect to import instance
data to instances, not aggregated data. A future DHIS2 Importer will
import tracked entity instances.

.. IMPORTANT::
   This code selects a ``ConnectionSettings`` instance by name, and
   assumes that it exists! See ``CONNECTION_SETTINGS_NAME`` in
   **const.py**.


I'm a TFM.
----------

If you are reading this, it's probably because something has changed in
DHIS2 or a CommCare app, and you need to change how DHIS2 data elements
are mapped to **facility_supervision** case properties. Edit the
**case_property_map.csv** file in Excel.

You are unlikely to know what to enter in the **data_set_id** column for
new case properties or data elements. There is a command named
**fetch_onse_dataset_ids** (in the **management/commands/** directory)
that will look up the data set IDs for the data elements in that file.

A developer will be able to help you with that, and deploy your changes.


I'm a dev.
----------

What does this code do?
^^^^^^^^^^^^^^^^^^^^^^^

Once a quarter, the ONSE ISS project needs to update case properties of
**facility_supervision** cases with totals collected in DHIS2 during the
previous quarter.

.. NOTE::
   Each **facility_supervision** case corresponds to a facility-level
   *organisation unit* in DHIS2. Its DHIS2 org unit ID is saved in
   the case's **external_id** case property.

**tasks.py** uses ``tasks.get_case_blocks()`` to iterate through
**facility_supervision** cases in the "onse-iss" domain. (These values
are set in **const.py**)

The ``tasks.set_case_updates()`` generator consumes the ``CaseBlock``s.
Each case corresponds to the *organisation unit* of a facility in DHIS2.
For each case property in **case_property_map.csv**,
``tasks.fetch_data_set()`` fetches its corresponding *data element's*
*data set* from DHIS2. It filters the query by the case's org unit ID to
get the data for the case's facility.

.. NOTE::
   A *data element* is an aggregated indicator. A *data set* is a
   collection of related *data elements*.

   Some *data elements* are broken down by *category options*. e.g. In
   DHIS2 demo data, the *data element* "Live births" is broken down by
   the *category* "Gender", which is given with the *category options*
   "Female" and "Male". The "Live births" *data element* belongs to the
   "Reproductive Health" *data set*. When we fetch the "Reproductive
   Health"*data set*, the "Live births" *data element* may be returned
   with separate counts for the "Female" *category option* and the
   "Male" *category option*.

   By requesting the *data set* of a *data element* from DHIS2, we are
   given all the *category options* that have had values submitted for
   them. We sum the values of the *data element's* *category options*
   to get the *data element's* total.

``set_case_updates()`` sets the case property value to the total of the
counts for all *category options* of the case property's *data element*.

Finally, the ``save_cases()`` function saves the ``CaseBlock``s in
chunks of 1000.


Management commands
^^^^^^^^^^^^^^^^^^^

You can use **fetch_onse_data_set_ids** to look up the *data set* IDs
for each *data element* in **case_property_map.csv**.

Use **update_onse_facility_cases** to pull last quarter's aggregated
data from DHIS2 on demand.
