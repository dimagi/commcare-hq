# Elasticsearch Reindex Process

This document outlines the process for reindexing an Elasticsearch index in CommCare HQ. The process would typically involve:
1. Creating a secondary index via migrations. ES migrations can be created by following [this](./README.rst#creating-elasticsearch-index-migrations) guide.
2. Updating [Secondary Index Names](./const.py#L27-L57) with the new secondary index names.
3. Multiplexing the HQ index adapters, so that data is written to both primary and secondary indices simultaneously using ElasticSyncMultiplexer.
4. Reindexing the secondary index using the `elastic_sync_multiplexed` utility.
5. Swapping the indices.
6. Turning off the multiplexer
7. Deleting the older index.
8. Updating [Index Names](https://github.com/dimagi/commcare-hq/blob/26ddc8f18f9a1c60c2aae6e09ecea4c4e6647758/corehq/apps/es/const.py#L27-L57), and setting primary index name to secondary index name and secondary index name to None.


### Prerequisites:

1. Ensure that there is enough free space available in your cluster. The command to estimate disk space required for reindexing is:

```sh
cchq <env> django-manage elastic_sync_multiplexed estimated_size_for_reindex
```

The output should look something like this

```
Index CName          | Index Name                     | Size on Disk         | Doc Count
-------------------- | ------------------------------ | -------------------- | ------------------------------
apps                 | apps-20230524                  | 2.34 GB              | 366291
cases                | cases-20230524                 | 9.69 GB              | 16354312
case_search          | case-search-20230524           | 76.97 GB             | 346089228
domains              | domains-20230524               | 6.61 MB              | 1491
forms                | forms-20230524                 | 16.32 GB             | 5506362
groups               | groups-20230524                | 739.49 KB            | 466
sms                  | sms-20230524                   | 216.47 MB            | 387294
users                | users-20230524                 | 293.24 MB            | 310403



Minimum free disk space recommended before starting the reindex: 126.99 GB

```

2. Check disk usage on each node

```sh
cchq <env>  run-shell-command <es_data_nodes> "df -h /opt/data" -b
```

This will return disk usage for each node. You can check if the cumulative available space across all nodes is greater than the total recommended space from the `estimated_size_for_reindex` output.

```
10.201.41.256 | CHANGED | rc=0 >>
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1     79G   19G   56G  26% /opt/data
10.201.40.228 | CHANGED | rc=0 >>
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1     79G   20G   55G  27% /opt/data
10.201.41.254 | CHANGED | rc=0 >>
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1     79G   19G   56G  26% /opt/data
```
In this case the available free space on all data nodes (56+55+56=167 GB) is greater than the recommended (126.99 GB) so the reindex can proceed. You can follow [Reindexing All Indices At Once](#reindexing-all-indices-at-once)
 process.

 If available disk size is less than recommended free space and it is not possible to increase the disk size then you can follow [Reindexing One Index At A Time](#reindexing-one-index-at-a-time) to reindex the indices.

3. Ensure that the new secondary indices are created and  [corehq.apps.es.const.py](./const.py) has updated `HQ_<index_cname>_SECONDARY_INDEX_NAME` variables with the new secondary index names that were created in migrations.

### Reindexing All Indices At Once.


1. In commcare cloud update `/environments/<env>/public.yml` with the following settings:
    ```
    ES_APPS_INDEX_MULTIPLEXED = True
    ES_CASE_SEARCH_INDEX_MULTIPLEXED = True
    ES_CASES_INDEX_MULTIPLEXED = True
    ES_DOMAINS_INDEX_MULTIPLEXED = True
    ES_FORMS_INDEX_MULTIPLEXED = True
    ES_GROUPS_INDEX_MULTIPLEXED = True
    ES_SMS_INDEX_MULTIPLEXED = True
    ES_USERS_INDEX_MULTIPLEXED = True
    ```

2. From control machine, run `update-config` and restart commcare services so that new settings are applied.
    ```
    cchq <env> update-config
    cchq <env> service commcare restart
    ```
    After these settings are applied all the adpaters will start writing to both primary and secondary indices simultaneously. Reads will still happen from the primary indices.

3. The following steps should be repeated for each value of the following values of <index_cname> -  'apps', 'cases', 'case_search', 'domains', 'forms', 'groups', 'sms', 'users'.

    1. Start the reindex process
        ```
        ./manage.py elastic_sync_multiplexed start <index_cname>
        ```
        It is advised to run the reindex command in a tmux session as it might take a long time and can be detached/re-attached as needed for monitoring progress.

        Note down the `task_number` that is displayed by the command. It should be a numeric ID and will be required to verify the reindex process

    2. Verify reindex is completed by querying the logs (only needed for Elasticsearch 2) and ensuring that doc count matches between primary and secondary indices.

        1. Logs can be queried by running:

            ```
            cchq <env> run-shell-command elasticsearch "grep '<task_id>.*ReindexResponse' /opt/data/elasticsearch*/logs/*.log"
            ```

            This command will query the Elasticsearch logs on all data nodes to find any log entries containing the ReindexResponse for the given task_id. The log should look something like:

            ```
            [2023-10-23 08:59:37,648][INFO] [tasks] 29216 finished with response ReindexResponse[took=1.8s,updated=0,created=1111,batches=2,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[],search_failures=[]]
            ```

            Ensure that `search_failures` and `indexing_failures` are empty lists.

        2. Then check doc counts between primary and secondary indices using:

            ```
            cchq env django-manage elastic_sync_multiplexed display_doc_counts <index_cname>
            ```

            This command will display the document counts for both the primary and secondary indices for a given index. If the doc count matches between the two and there are no errors in the reindex logs, then reindexing is complete for that index.

            Please note that for high frequency indices like case_search, cases, and forms the counts may not match perfectly. In such cases, ensure the difference in counts is small (within one hundred) and there are no errors in reindex logs.

    3.  After the index has been reindexed, for every index cname, run the following commands to cleanup tombstones and set the correct replica count for the newly created index.
        ```
        ./manage.py elastic_sync_multiplexed cleanup <index_cname>
        ```

        ```
        ./manage.py elastic_sync_multiplexed set_replicas <index_cname>
        ```

4. At this point we should have a secondary index for every primary index. Writes will continue to happen to both primary and secondary indices simultaneously. Reads will still happen from the primary index.

5. To switch the reads from the primary index to the new secondary index, we need to swap the indices.
To swap the indexes we need to follow the following steps:

    1. Stop the pillows

        ```
        cchq <env> service pillowtop stop
        ```
    2. Copy the checkpoint ids for the pillows that depend on the index you are about to swap. For every index_cname run:

        ```
        cchq <env> django-manage elastic_sync_multiplexed copy_checkpoints <index_cname>
        ```
    3. Swap the indexes in settings to make the primary index the secondary index and vice versa.
    Update `environments/<env>/public.yml`, set
        ```
        ES_APPS_INDEX_SWAPPED = True
        ES_CASE_SEARCH_INDEX_SWAPPED = True
        ES_CASES_INDEX_SWAPPED = True
        ES_DOMAINS_INDEX_SWAPPED = True
        ES_FORMS_INDEX_SWAPPED = True
        ES_GROUPS_INDEX_SWAPPED = True
        ES_SMS_INDEX_SWAPPED = True
        ES_USERS_INDEX_SWAPPED = True
        ```
    4. From the control machine, run `update-config` and restart commcare services so that the new settings are applied. This will also restart the pillows that were stopped in the previous step.
        ```
        cchq <env> update-config
        cchq <env> service commcare restart
        ```
        After this step, the indexes will be swapped and reads will now happen from the newly created secondary indices.

    5. Open CommCare HQ to test features that interact with Elasticsearch. One example is submitting a form and then ensuring that that form submission appears in relevant reports. If you have metrics setup for pillows, verify that the change feed is looking good.

    6. It is recommended to keep the indices in this state for at least 2 working days. This will provide a safe window to fall back if needed.

6. When you are confident that things are working fine with the new index, you are all set to turn off the multiplexer settings. Update `environments/<env>/public.yml` with following values:
    ```
    ES_APPS_INDEX_MULTIPLEXED = False
    ES_CASE_SEARCH_INDEX_MULTIPLEXED = False
    ES_CASES_INDEX_MULTIPLEXED = False
    ES_DOMAINS_INDEX_MULTIPLEXED = False
    ES_FORMS_INDEX_MULTIPLEXED = False
    ES_GROUPS_INDEX_MULTIPLEXED = False
    ES_SMS_INDEX_MULTIPLEXED = False
    ES_USERS_INDEX_MULTIPLEXED = False
    ```

    From the control machine, run `update-config` and restart commcare services so that new settings are applied.

    ```
    cchq <env> update-config
    cchq <env> service commcare restart
    ```

7. At this stage, writes have been stopped on the older indices. The older indices are eligible for deletion. It is recommended to wait for 6 hours after the multiplexer is turned off. The older indices can be deleted by running.

    ```
    cchq <env> django-manage elastic_sync_multiplexed delete <index_cname>
    ```
8. Delete any lingering residual indices by running

```
cchq <env> django-manage elastic_sync_multiplexed remove_residual_indices
```
These indices are safe to delete and are not used in any functionality of CommCare HQ.

9. Congratulations :tada: You have successfully created new indexes that are active on CommCare HQ.

10. Update [Index Names](./const.py#L27-L57), set Primary index names to secondary index name and secondary index names to `None`.

11. Set Index swapped variables to False

    ```
    ES_APPS_INDEX_SWAPPED = False
    ES_CASE_SEARCH_INDEX_SWAPPED = False
    ES_CASES_INDEX_SWAPPED = False
    ES_DOMAINS_INDEX_SWAPPED = False
    ES_FORMS_INDEX_SWAPPED = False
    ES_GROUPS_INDEX_SWAPPED = False
    ES_SMS_INDEX_SWAPPED = False
    ES_USERS_INDEX_SWAPPED = False

    ```

12. Before deploying the changes in Step 10, run `update-config`.

    ```
    cchq <env> update-config
    ```

13. Deploy Commcare HQ.

    ```
    cchq <env> deploy
    ```


### Reindexing One Index At A Time

When there isn't enough space to accomodate duplicate data for all the indices, then we will multiplex, reindex and swap one index at a time. Then we will turn off the multiplexer, swap the index, and delete the older index. We will then repeat this process for all of the indices as described below.

1.  To turn on multiplexer one index at a time, repeat the following steps by replacing <index_cname> with the following values

    ```
    'apps', 'cases', 'case_search', 'domains', 'forms', 'groups', 'sms', 'users'
    ```

    1. Update `environments/<env>/public.yml`.
        ```
        ES_<index_cname>_INDEX_MULTIPLEXED = True
        ```
    2. Apply the changes and restart commcare service

        ```
        cchq <env> update-config
        cchq <env> service commcare restart
        ```
    3. Start the reindex process for <index_cname>
        ```
        ./manage.py elastic_sync_multiplexed start <index_cname>
        ```
        It is advised to run the reindex command in a tmux session as it might take a long time and can be detached/re-attached as needed for monitoring progress.

        Note down the `task_number` that is displayed by the command. It should be a numeric ID and will be required to verify the reindex process

    4. Verify reindex is completed by querying the logs (only needed for Elasticsearch 2) and ensuring that the doc count matches between primary and secondary indices.

        1. Logs can be queried by running:

            ```
            cchq <env> run-shell-command elasticsearch "grep '<task_number>.*ReindexResponse' /opt/data/elasticsearch*/logs/*.log"
            ```

            This command will query the Elasticsearch logs on all data nodes to find any log entries containing the ReindexResponse for the given task_number. The log should look something like:

            ```
            [2023-10-23 08:59:37,648][INFO] [tasks] 29216 finished with response ReindexResponse[took=1.8s,updated=0,created=1111,batches=2,versionConflicts=0,noops=0,retries=0,throttledUntil=0s,indexing_failures=[],search_failures=[]]
            ```

            Ensure that `search_failures` and `indexing_failures` are empty lists.

        2. Then check doc counts between primary and secondary indices using:

            ```
            cchq env django-manage elastic_sync_multiplexed display_doc_counts <index_cname>
            ```

            This command will display the document counts for both the primary and secondary indices for a given index. If the doc count matches between the two and there are no errors in the reindex logs, then reindexing is complete for that index.

            Please note that for high frequency indices like case_search, cases, and forms, the counts may not match perfectly. In such cases, ensure the difference in counts is small (within one hundred) and there are no errors in reindex logs.

    5.  After the index has been reindexed, we need to cleanup tombstones and set the correct replica count for the newly created index.
        ```
        ./manage.py elastic_sync_multiplexed cleanup <index_cname>
        ```

        ```
        ./manage.py elastic_sync_multiplexed set_replicas <index_cname>
        ```
    6. At this step we should have a secondary index for `<index_cname>` which has the same data as the primary index. On index `<index_cname>` writes will continue to happen to both primary and secondary indices simultaneously. Reads will still hit the primary index.

    7. To switch the reads from the primary index to the new secondary index, we need to swap the index.
    To swap the index we need to follow the following steps:

        1. Stop the pillows

            ```
            cchq <env> service pillowtop stop
            ```
        2. Copy the checkpoint ids for the pillows that depend on the index you are about to swap.

            ```
            cchq <env> django-manage  elastic_sync_multiplexed copy_checkpoints <index_cname>
            ```
        3. We will now swap the index in the settings file to  make the primary index as secondary and vice versa.
        Update `environments/<env>/public.yml`, set
            ```
            ES_<index_cname>_INDEX_SWAPPED = True
            ```

        4. From the control machine, run update-config and restart commcare services so that the new settings are applied. This will also restart the pillows that were stopped in the previous step.
            ```
            cchq <env> update-config
            cchq <env> service commcare restart
            ```
            After this step, the indexes will be swapped and reads will now happen from the newly created secondary index.

        5. Look around in CommcareHQ, test out things dealing with the index that was swapped

        6. It is recommended to keep the index in this state for at least 1 working day. This will provide a safe window to fall back if needed.

    8. When you are confident that things are working fine with the new index, you are all set to turn off the multiplexer settings. Update `environments/<env>/public.yml` with following values:
        ```
        ES_<index_cname>_INDEX_MULTIPLEXED = False
        ```
    9. For index <index_cname>, writes have been stopped on the old primary index. The older index is eligible for deletion. It is recommended to wait for 6 hours after the multiplexer is turned off. The older index can be deleted by running.

    ```
    cchq <env> django-manage elastic_sync_multiplexed delete <index_cname>
    ```
    This will free up the space on machine and you are ready to reindex another index.

    10. Go back to Step 1 and repeat the process with a different index_cname

2. Delete any lingering residual indices by running

```
cchq <env> django-manage elastic_sync_multiplexed remove_residual_indices
```
These indices are safe to delete and are not used in any functionality of CommCareHQ.

3. Congratulations :tada: You have successfully created new indexes that are active on CommcareHQ.

4. Update [Index Names](./const.py#L27-L57), set primary index names to secondary index name and secondary index names to `None`.

5. Set Index swapped variables to False

    ```
    ES_APPS_INDEX_SWAPPED = False
    ES_CASE_SEARCH_INDEX_SWAPPED = False
    ES_CASES_INDEX_SWAPPED = False
    ES_DOMAINS_INDEX_SWAPPED = False
    ES_FORMS_INDEX_SWAPPED = False
    ES_GROUPS_INDEX_SWAPPED = False
    ES_SMS_INDEX_SWAPPED = False
    ES_USERS_INDEX_SWAPPED = False

    ```

6. Before deploying the changes in Step 10, run `update-config`.

    ```
    cchq <env> update-config
    ```

7. Deploy Commcare HQ.

    ```
    cchq <env> deploy
    ```


### Common Issues Resolutions During Reindex

#### ReIndex logs does not have error but doc counts don't match

If the reindex log has no errors but the doc counts don't match, it might be the case that one of the Elasticsearch machine ran out of memory and got restarted.

You can verify this by querying the logs -
```
cchq <env> run-shell-command elasticsearch 'grep -r -i "java.lang.OutOfMemoryError" /opt/data/elasticsearch-*/logs -A10'
```
By default elasticsearch uses a batch size of 1000 and if there are big docs then this can cause memory issues if cluster is running low on memory. You can try decreasing the `batch_size` to a smaller number while starting the reindex process.

```
./manage.py elastic_sync_multiplexed start <index_cname> --batch_size <batch size>
```

This might increase the reindex time but can avoid OOM errors.

#### ReIndex logs have BulkItemResponseFailure

If the reindex logs have `BulkItemResponse$Failure` then it can be because of `_id` being present in `_source` objects. You can query detailed logs by running :

```
cchq production run-shell-command elasticsearch 'grep -r -i "failed to execute bulk item (index) index" /opt/data/elasticsearch-2.4.6/logs -A20'
```

If the logs contains following error

```
MapperParsingException[Field [_id] is a metadata field and cannot be added inside a document. Use the index API request parameters]
```

The issue can be fixed by passing `--purge-ids` argument to the `reindex` command. This will remove `_id` from documents during reindexing to avoid these errors.

```
./manage.py elastic_sync_multiplexed start <index_cname> --purge-ids
```

#### Unable to assign replicas

While assigning replicas if you get the following error in es logs -

```
[2023-10-03 14:31:09,981][INFO ][cluster.routing.allocation.decider] [esmaster_a1] low disk watermark [85%] exceeded on [Ap_smchPTLinFxB2BPWpJw][es-machine-env][/opt/data/elasticsearch-2.4.6/data/enves-2.x/nodes/0] free: 258.4gb[12.5%], replicas will not be assigned to this node
```

You can increase the watermark settings to a higher value like:

```
curl -X PUT "http://<cluster_ip>:9200/_cluster/settings" -H "Content-Type: application/json" -d '{
  "persistent": {
    "cluster.routing.allocation.disk.watermark.low": "95%",
    "cluster.routing.allocation.disk.watermark.high": "97.5%"
  }
}'
```

This will update the Elasticsearch cluster settings to set the disk watermark thresholds higher (to 95% low and 97.5% high from default), allowing replicas to be assigned even when disk usage reaches those levels.

After the replicas are assigned, you can reset the disk watermark thresholds back to the default values by running:

```
curl -X PUT "http://<cluster_ip>:9200/_cluster/settings" -H "Content-Type: application/json" -d '{
  "persistent": {
    "cluster.routing.allocation.disk.watermark.low": "85%",
    "cluster.routing.allocation.disk.watermark.high": "90%"
  }
}'
```

If reindex fails with out of memory errors, then batch size can be decreased while running reindex

```
    ./manage.py elastic_sync_multiplexed start <index_cname> --batch_size <batch size>
```