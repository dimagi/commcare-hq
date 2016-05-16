DROP FUNCTION IF EXISTS get_ledger_values_for_product_ids(TEXT[]);

-- RUN ON ALL must return SETOF
CREATE FUNCTION get_ledger_values_for_product_ids(p_product_ids TEXT[]) RETURNS SETOF form_processor_ledgervalue AS $$
    CLUSTER '{{ PL_PROXY_CLUSTER_NAME }}';
    RUN ON ALL;
$$ LANGUAGE plproxy;

