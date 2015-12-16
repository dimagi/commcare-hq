HQ Management Commands
=======================

..
    Please add to and edit this doc as you see fit.
    Running the --help command will give you a docstring you can use
    in the definition.
    Include usage or an example if it's not obvious.
    Let's keep the definitions alphabetical for now, or else break it
    into logical sections.


This is a list of useful management commands.  They can be run using
``$ python manage.py <command>`` or ``$ ./manage.py <command>``.
For more information on a specific command, run
``$ ./manage.py <command> --help``

**bootstrap**
    Bootstrap a domain and user who owns it.
    Usage::
    $ ./manage.py bootstrap [options] <domain> <email> <password>

**bootstrap_app**
    Bootstrap an app in an existing domain.
    Usage::
    $ ./manage.py bootstrap_app [options] <domain_name> <app_name>

**clean_pyc**
    Removes all python bytecode (.pyc) compiled files from the project.

**copy_domain**
    Copies the contents of a domain to another database.
    Usage:: 
    $ ./manage.py copy_domain [options] <sourcedb> <domain>

**ptop_fast_reindex_fluff**
    Fast reindex of fluff docs.
    Usage::
    $ ./manage.py ptop_fast_reindex_fluff [options] <domain> <pillow_class>

**run_ptop**
    Run the pillowtop management command to scan all _changes feeds

**runserver**
    | Starts a lightweight web server for development which outputs additional debug information.
    | ``--werkzeug``  Tells Django to use the Werkzeug interactive debugger.

**syncdb**
    | Create the database tables for all apps in INSTALLED_APPS whose tables haven't already been created, except those which use migrations.
    | ``--migrate`` Tells South to also perform migrations after the sync.

**test**
    Runs the test suite for the specified applications, or the entire site if no apps are specified.
    Usage::
    $ ./manage.py test [options] [appname ...]


----------------------------------------------------------------

Complete list of available subcommands:
    | add_case_properties
    | add_commcare_build
    | add_pie_chart_report
    | backup_db
    | bihar_dump_indicators
    | bihar_print_groups
    | bihar_run_calcs
    | bootstrap
    | bootstrap_app
    | bootstrap_psi
    | build_apps
    | camqadm
    | celery
    | celerybeat
    | celerycam
    | celeryctl
    | celeryd
    | celeryd_detach
    | celeryd_multi
    | celeryev
    | celerymon
    | changepassword
    | check_case_verified_numbers
    | clean_couchlog
    | clean_pyc
    | cleanup
    | clear_supervisor_confs
    | collectstatic
    | compact_views
    | compile_pyc
    | compilemessages
    | compute_diffs
    | constants
    | convert_to_south
    | copy_doc
    | copy_doc_types
    | copy_domain
    | copy_group_data
    | couchexport_data
    | create_app
    | create_command
    | create_definitions_2012_04
    | create_definitions_2012_07
    | create_jobs
    | createcachetable
    | createsuperuser
    | datamigration
    | dbshell
    | delete_db
    | delete_location
    | describe_form
    | diffsettings
    | djcelerymon
    | dumpdata
    | dumpscript
    | export_emails
    | find_broken_suite_files
    | find_template
    | findstatic
    | flush
    | force_update_schemas
    | forms_without_domains
    | generate_form_case_consistency_list
    | generate_secret_key
    | graph_models
    | graphmigrations
    | hide_docs
    | hsph_delete_test_data
    | inspectdb
    | kill_cloudant
    | loaddata
    | mail_admins
    | mail_debug
    | make_supervisor_conf
    | makemessages
    | migrate
    | migrate_backends
    | migrate_case_export_tags
    | migrate_custom_exports
    | migrate_domain_names
    | migrate_domain_to_couch
    | migrate_export_types
    | migrate_include_errors
    | migrate_loc_code
    | migrate_message_log
    | migrate_registration_request_to_couch
    | migrate_reminders_2012_04
    | migrate_smslog_2012_04
    | migrate_surveysample_group_2013_09
    | mkapacheconf
    | mkserverinstance
    | mvp_force_update
    | mvp_make_couch_indicators
    | mvp_make_indicators
    | mvp_test
    | notes
    | opm_test_data
    | pact_00_import_users
    | pact_01_bootstrap_cases
    | pact_02_import_providers
    | pact_02b_verify_fix_regimens
    | pact_03_case_final_ota
    | pact_04_update_patient_schedules
    | pact_05_apply_roles
    | pact_05b_apply_user_props
    | pact_06_case_spec
    | pact_07_final_dot_compute
    | pact_09_compact
    | pact_compute_dots
    | pact_import_complete
    | pact_import_create_domain
    | pact_import_submissions
    | pact_test_dots_labels
    | passwd
    | patch_submissions
    | pipchecker
    | post_form
    | preindex_everything
    | prime_views
    | print_settings
    | print_user_for_session
    | ptop_es_manage
    | ptop_fast_reindex_apps
    | ptop_fast_reindex_cases
    | ptop_fast_reindex_domains
    | ptop_fast_reindex_fluff
    | ptop_fast_reindex_fullcases
    | ptop_fast_reindex_fullxforms
    | ptop_fast_reindex_reportcases
    | ptop_fast_reindex_reportxforms
    | ptop_fast_reindex_smslogs
    | ptop_fast_reindex_users
    | ptop_fast_reindex_xforms
    | ptop_fast_reindexer
    | ptop_generate_mapping
    | ptop_make_app_mapping
    | ptop_make_case_mapping
    | ptop_make_domain_mapping
    | ptop_make_fullcase_mapping
    | ptop_make_fullxform_mapping
    | ptop_make_reportcase_mapping
    | ptop_make_reportxform_mapping
    | ptop_make_sms_mapping
    | ptop_make_user_mapping
    | ptop_make_xform_mapping
    | ptop_preindex
    | ptop_reset_checkpoint
    | purgestale
    | rebuild_case
    | recalculate_sms_billing
    | recent_changes
    | record_deploy_success
    | redo_sms_in_bills
    | reindex_views
    | remove_duplicate_domains
    | replicate_couchdb
    | reprocess_error_form
    | reprocess_error_formlist
    | reprocess_error_forms
    | reset
    | reset_db
    | resolve_urls
    | run_gunicorn
    | run_ptop
    | runfcgi
    | runjob
    | runjobs
    | runprofileserver
    | runscript
    | runserver
    | runserver_plus
    | schemamigration
    | script_case_attachment
    | seltest
    | set_fake_emails
    | set_fake_passwords
    | shell
    | shell_plus
    | show_templatetags
    | show_urls
    | slay_unicorns
    | sql
    | sqlall
    | sqlclear
    | sqlcreate
    | sqlcustom
    | sqldiff
    | sqlflush
    | sqlindexes
    | sqlinitialdata
    | sqlreset
    | sqlsequencereset
    | staging_replicate
    | staging_replicate_admin
    | startapp
    | startmigration
    | submit_form
    | submit_forms
    | sync_couch_users_to_sql
    | sync_couchdb
    | sync_finish_couchdb
    | sync_finish_couchdb_hq
    | sync_media_s3
    | sync_prepare_couchdb
    | sync_prepare_couchdb_multi
    | syncdata
    | syncdb
    | test
    | test_reports
    | testproject
    | testserver
    | unreferenced_files
    | update_permissions
    | update_schema_checkpoints
    | utils
    | validate
    | validate_templates
