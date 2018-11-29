-- prevent inserts of legacy form and case attachments
CREATE OR REPLACE FUNCTION insert_not_allowed() RETURNS TRIGGER AS $$ BEGIN
    RAISE EXCEPTION 'insert not allowed';
END; $$ LANGUAGE 'plpgsql';

DROP TRIGGER IF EXISTS legacy_xform_attachment_insert_not_allowed
    ON form_processor_xformattachmentsql;

CREATE TRIGGER legacy_xform_attachment_insert_not_allowed
    BEFORE INSERT ON form_processor_xformattachmentsql
    EXECUTE PROCEDURE insert_not_allowed();
