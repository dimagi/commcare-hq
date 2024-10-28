Migrating to Mobile UCR Restore V2
==================================

Evolution of Mobile UCR Restore Versions
----------------------------------------
Historically, there were three configuration settings for how Mobile UCRs were sent to devices:

- Version 1.0: Bundled all reports into a single fixture during the restore process.
- Version 1.5: Sent both V1 and V2 restore formats.
- Version 2.0: Split UCRs into multiple fixtures within the restore.

Deprecation of Mobile UCR V1 and V1.5
-------------------------------------
Both V1 and V1.5 to address performance challenges encountered with these versions.
The primary issue with V1 was that all UCRs were bundled into a single fixture, meaning any change to a
single report required resyncing the entire fixture, leading to slow and inefficient restore processes.
This bundling often caused unnecessary server load and sluggish syncing for mobile users.

Benefits of Upgrading to Mobile UCR V2
--------------------------------------
The introduction of Mobile UCR V2 brings significant improvements, especially around how
UCR data is restored and synced:

- Multiple Fixtures: Instead of bundling all reports into one fixture, UCRs are now split into multiple fixtures. Each fixture corresponds to a specific report and its filters. This allows for:
    - *Faster Lookups*: Because reports are no longer combined, users can access specific data more quickly. Individual Updates: Reports can be updated separately, reducing the need to sync the entire set of reports.
    - *App-Aware Restores*: V2 also introduces “app-aware” restores, where only the fixtures relevant to the specific app being used are synced. This targeted sync ensures that only necessary data is processed, further improving efficiency.
- Sync Delay Option: V2 includes a "Sync Delay" option for each report, allowing administrators to control how frequently report data is synced. For reports that can tolerate slightly outdated (or “stale”) data this feature reduces the load on the server and the device:
    - *Performance Improvements*: Syncing less often reduces the time required for the restore process. User Experience: Users experience fewer interruptions, allowing them to continue their work with minimal delays in syncing reports.

Moving to Mobile UCR V2
-----------------------
- It is recommended to remove any older app versions (especially older than 2 years) that the project has
  no use for. This will lessen the chances of having to update very old projects in the case of releasing
  a previous version.
- Applications that do not have any references to UCRs in forms, case lists and filters need only have their
  Mobile UCR Version updated to V2 and the app will continue working as normal.
- Applications with references to reports will need to have all manual references to the `commcare:reports`
  fixture changed before updating to V2. These are most likely to be contained in reports modules,
  but others may be in case lists.

Update Mobile UCR Version
-------------------------
In the app settings, in the "Advanced Setting" tab, you'll find "Mobile UCR Restore Version".
Set the version to '2.0' if your application does not have any references to UCRs.

.. image:: ../images/mobile_ucr_restore_version_2_setting.png

Update Application manual references
------------------------------------
Applications with references to reports will need to have all manual references to
the `commcare:reports` fixture changed before updating to V2.

To do this, you will need the UUID for each report which can be found in the Reports
module in the report definition.

.. image:: ../images/mobile_ucr_report_uuid.png

You can change any reports references by using this format as a guide
("c47c48..." is the UUID for the example report)

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * -
     - V1
     - V2
   * - **Report references**
     - ``instance('reports')/reports/report[@id='xxxxxxx']``

       ``instance('reports')/reports/report[@id='c47c48993851c09a152b91614ee1f6592fc2dd37']/rows/row[@is_total_row='False']``
     - ``instance('commcare-reports:xxxxxxx')``

       ``instance('commcare-reports:c47c48993851c09a152b91614ee1f6592fc2dd37')/rows/row[@is_total_row='False']``
   * - **Filters**
     - ``column[@id='Report Column ID'] = value``

       ``column[@id='computed_owner_name_40cc88a0'] = instance('commcaresession')/session/data/report_filter_c47c48993851c09a152b91614ee1f6592fc2dd37_computed_owner_name_40cc88a0_1``
     - ``Report Column ID = value``

       ``computed_owner_name_40cc88a0 = instance('commcaresession')/session/data/report_filter_c47c48993851c09a152b91614ee1f6592fc2dd37_computed_owner_name_40cc88a0_1``
   * - **Column references**
     - ``column[@id='Report Column ID']``

       ``column[@id='computed_owner_name_40cc88a0']``
     - ``Report Column ID``

       ``computed_owner_name_40cc88a0``
