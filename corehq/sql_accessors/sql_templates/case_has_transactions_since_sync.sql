DROP FUNCTION IF EXISTS case_has_transactions_since_sync(text, text, timestamp with time zone);

CREATE FUNCTION case_has_transactions_since_sync(p_case_id text, p_sync_log_id text, sync_log_date timestamp with time zone)
RETURNS boolean AS $$
BEGIN
    RETURN (
      SELECT EXISTS(
        SELECT TRUE FROM form_processor_casetransaction AS transaction_table
          WHERE transaction_table.case_id = p_case_id
            AND transaction_table.server_date > sync_log_date
            AND transaction_table.sync_log_id IS DISTINCT FROM p_sync_log_id
            LIMIT 1
      )
    );
END;
$$ LANGUAGE plpgsql;
