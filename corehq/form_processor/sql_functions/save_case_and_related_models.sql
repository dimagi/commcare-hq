DROP FUNCTION IF EXISTS save_case_and_related_models(
    form_processor_commcarecasesql,
    form_processor_casetransaction[],
    form_processor_commcarecaseindexsql[],
    form_processor_caseattachmentsql[],
    INTEGER[],
    INTEGER[]
);

CREATE FUNCTION save_case_and_related_models(
    commcarecase form_processor_commcarecasesql,
    transactions form_processor_casetransaction[],
    indices form_processor_commcarecaseindexsql[],
    attachments form_processor_caseattachmentsql[],
    indices_to_delete INTEGER[],
    attachements_to_delete INTEGER[],
    case_pk OUT INTEGER
) AS $$
DECLARE
    case_transaction form_processor_casetransaction;
    case_index form_processor_commcarecaseindexsql;
    attachment form_processor_caseattachmentsql;
    attachement_id_to_delete INTEGER;
    index_id_to_delete INTEGER;
BEGIN
    IF commcarecase.id IS NOT NULL THEN
        UPDATE form_processor_commcarecasesql SET
            domain = commcarecase.domain,
            type = commcarecase.type,
            name = commcarecase.name,
            owner_id = commcarecase.owner_id,
            opened_on = commcarecase.opened_on,
            opened_by = commcarecase.opened_by,
            modified_on = commcarecase.modified_on,
            modified_by = commcarecase.modified_by,
            server_modified_on = commcarecase.server_modified_on,
            closed = commcarecase.closed,
            closed_on = commcarecase.closed_on,
            closed_by = commcarecase.closed_by,
            deleted = commcarecase.deleted,
            external_id = commcarecase.external_id,
            location_id = commcarecase.location_id,
            case_json = commcarecase.case_json
        WHERE
            case_id = commcarecase.case_id
        RETURNING form_processor_commcarecasesql.id INTO case_pk;
    ELSE
        INSERT INTO form_processor_commcarecasesql (
            case_id,
            domain,
            type,
            name,
            owner_id,
            opened_on,
            opened_by,
            modified_on,
            modified_by,
            server_modified_on,
            closed,
            closed_on,
            closed_by,
            deleted,
            external_id,
            location_id,
            case_json
        ) VALUES (
            commcarecase.case_id,
            commcarecase.domain,
            commcarecase.type,
            commcarecase.name,
            commcarecase.owner_id,
            commcarecase.opened_on,
            commcarecase.opened_by,
            commcarecase.modified_on,
            commcarecase.modified_by,
            commcarecase.server_modified_on,
            commcarecase.closed,
            commcarecase.closed_on,
            commcarecase.closed_by,
            commcarecase.deleted,
            commcarecase.external_id,
            commcarecase.location_id,
            commcarecase.case_json
        ) RETURNING form_processor_commcarecasesql.id INTO case_pk;
    END IF;

    -- delete old models
    FOREACH attachement_id_to_delete in ARRAY attachements_to_delete
    LOOP
        DELETE from form_processor_caseattachmentsql where id = attachement_id_to_delete;
    END LOOP;

    FOREACH index_id_to_delete in ARRAY indices_to_delete
    LOOP
        DELETE from form_processor_commcarecaseindexsql where id = index_id_to_delete;
    END LOOP;

    -- insert new transactions
    FOREACH case_transaction IN ARRAY transactions
    LOOP
        IF case_transaction.id IS NOT NULL THEN
            RAISE EXCEPTION 'Updating case transactions is not supported. case id=%s, transaction id=%s',
                commcarecase.case_id, case_transaction.id;
        ELSE
            INSERT INTO form_processor_casetransaction (
                form_id, sync_log_id, server_date, type,
                case_id, revoked, details
            ) VALUES (
                case_transaction.form_id, case_transaction.sync_log_id, case_transaction.server_date, case_transaction.type,
                case_transaction.case_id, case_transaction.revoked, case_transaction.details
            );
        END IF;
    END LOOP;

    -- insert new indices
    FOREACH case_index IN ARRAY indices
    LOOP
        IF case_index.id IS NOT NULL THEN
            UPDATE form_processor_commcarecaseindexsql SET
                referenced_id = case_index.referenced_id,
                referenced_type = case_index.referenced_type,
                relationship_id = case_index.relationship_id
            WHERE
                id = case_index.id;
        ELSE
            INSERT INTO form_processor_commcarecaseindexsql (
                domain, identifier, referenced_id,
                referenced_type, relationship_id, case_id
            ) VALUES (
                case_index.domain, case_index.identifier, case_index.referenced_id,
                case_index.referenced_type, case_index.relationship_id, case_index.case_id
            );
        END IF;
    END LOOP;

    -- insert new attachments
    FOREACH attachment IN ARRAY attachments
    LOOP
        IF attachment.id IS NOT NULL THEN
            RAISE EXCEPTION 'Updating attachments is not supported. case id=%s, attachment id=%s',
                commcarecase.case_id, attachment.attachment_id;
        ELSE
            INSERT INTO form_processor_caseattachmentsql (
                attachment_id, name, content_type, md5, case_id
            ) VALUES (
                attachment.attachment_id, attachment.name, attachment.content_type, attachment.md5, attachment.case_id
            );
        END IF;
    END LOOP;
END
$$
LANGUAGE 'plpgsql';
