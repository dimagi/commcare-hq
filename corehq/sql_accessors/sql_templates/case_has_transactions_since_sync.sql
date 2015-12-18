DROP FUNCTION IF EXISTS case_has_transactions_since_sync(text, text, timestamp with time zone);

CREATE FUNCTION case_has_transactions_since_sync(p_case_id text, p_sync_log_id text, sync_log_date timestamp with time zone)
  RETURNS boolean AS $$
    SELECT EXISTS(
      SELECT TRUE FROM form_processor_casetransaction AS transaction_table
        WHERE transaction_table.case_id = $1
          AND transaction_table.server_date > $3
          AND transaction_table.sync_log_id IS DISTINCT FROM $2
    );
$$ LANGUAGE sql;
