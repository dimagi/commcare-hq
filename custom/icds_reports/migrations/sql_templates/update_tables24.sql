CREATE TABLE icds_dashboard_inactive_aww
(
  awc_id text NOT NULL,
  awc_name text,
  awc_site_code text,
  supervisor_id text,
  supervisor_name text,
  block_id text,
  block_name text,
  district_id text,
  district_name text,
  state_id text,
  state_name text,
  first_submission date,
  last_submission date,
  CONSTRAINT "icds_dashboard_inactive_awws_pkay" PRIMARY KEY (awc_id)
);
