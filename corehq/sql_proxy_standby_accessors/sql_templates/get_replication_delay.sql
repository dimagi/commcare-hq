DROP FUNCTION IF EXISTS get_replication_delay();

CREATE FUNCTION get_replication_delay() RETURNS TABLE (database text, replication_delay INTEGER)  AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
    SELECT
    current_database() as database,
    CASE
        WHEN NOT EXISTS (SELECT 1 FROM pg_stat_wal_receiver) THEN -1
        WHEN pg_last_xlog_receive_location() = pg_last_xlog_replay_location() THEN 0
        ELSE EXTRACT (EPOCH FROM now() - pg_last_xact_replay_timestamp())::INTEGER
    END
    AS replication_delay;
$$ LANGUAGE plproxy;
