DROP FUNCTION IF EXISTS save_new_form_with_attachments(form_processor_xforminstancesql, form_processor_xformattachmentsql[]);

CREATE FUNCTION save_new_form_with_attachments(
    form form_processor_xforminstancesql,
    attachments form_processor_xformattachmentsql[],
    form_pk OUT INTEGER
) AS $$
DECLARE
    attachment form_processor_xformattachmentsql;
BEGIN
    INSERT INTO form_processor_xforminstancesql (
        form_id,
        domain,
        app_id,
        xmlns,
        user_id,
        orig_id,
        deprecated_form_id,
        edited_on,
        received_on,
        auth_context,
        openrosa_headers,
        partial_submission,
        submit_ip,
        last_sync_token,
        problem,
        date_header,
        build_id,
        state,
        initial_processing_complete
    )
    VALUES (
        form.form_id,
        form.domain,
        form.app_id,
        form.xmlns,
        form.user_id,
        form.orig_id,
        form.deprecated_form_id,
        form.edited_on,
        form.received_on,
        form.auth_context,
        form.openrosa_headers,
        form.partial_submission,
        form.submit_ip,
        form.last_sync_token,
        form.problem,
        form.date_header,
        form.build_id,
        form.state,
        form.initial_processing_complete
    ) RETURNING form_processor_xforminstancesql.id INTO form_pk;

    FOREACH attachment IN ARRAY attachments
    LOOP
        INSERT INTO form_processor_xformattachmentsql (
            attachment_id, name, content_type, md5, form_id
        ) VALUES (
            attachment.attachment_id, attachment.name, attachment.content_type, attachment.md5, attachment.form_id
        );
    END LOOP;
END
$$
LANGUAGE 'plpgsql';
