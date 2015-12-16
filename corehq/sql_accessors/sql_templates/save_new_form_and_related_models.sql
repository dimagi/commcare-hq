DROP FUNCTION IF EXISTS save_new_form_and_related_models(
    TEXT,
    form_processor_xforminstancesql,
    form_processor_xformattachmentsql[],
    form_processor_xformoperationsql[]);

CREATE FUNCTION save_new_form_and_related_models(
    p_form_id TEXT,
    form form_processor_xforminstancesql,
    attachments form_processor_xformattachmentsql[],
    operations form_processor_xformoperationsql[],
    form_pk OUT INTEGER
) AS $$
DECLARE
    attachment form_processor_xformattachmentsql;
    operation form_processor_xformoperationsql;
BEGIN
    IF form.id IS NOT NULL THEN
        RAISE EXCEPTION 'Form already saved: %', form.form_id;
    END IF;

    IF p_form_id <> form.form_id THEN
        RAISE EXCEPTION 'form_id parameter not equal to XFormInstance.form_id';
    END IF;


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
        IF attachment.id IS NOT NULL THEN
            RAISE EXCEPTION 'Form attachment already saved: form_id=%, attachment_id=%', form.form_id, attachment.attachment_id;
        END IF;

        INSERT INTO form_processor_xformattachmentsql (
            attachment_id, name, content_type, md5, form_id
        ) VALUES (
            attachment.attachment_id, attachment.name, attachment.content_type, attachment.md5, attachment.form_id
        );
    END LOOP;

    FOREACH operation IN ARRAY operations
    LOOP
        IF operation.id IS NOT NULL THEN
            RAISE EXCEPTION 'Form operation already saved: form_id=%, operation_id=%', form.form_id, operation.id;
        END IF;

        INSERT INTO form_processor_xformoperationsql (user_id, operation, date, form_id) VALUES
            (operation.user_id, operation.operation, operation.date, operation.form_id);
    END LOOP;
END
$$
LANGUAGE 'plpgsql';
