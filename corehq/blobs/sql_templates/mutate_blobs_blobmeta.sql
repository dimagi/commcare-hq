CREATE OR REPLACE FUNCTION mutate_blobs_blobmeta() RETURNS TRIGGER AS $$ BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW."id" IS NULL THEN
            NEW."id" := NEXTVAL('blobs_blobmeta_id_seq');
        ELSIF NEW."id" < 0 THEN
            RAISE EXCEPTION 'Negative id not allowed';
        END IF;
        INSERT INTO blobs_blobmeta_tbl (
            "id",
            "domain",
            "parent_id",
            "name",
            "key",
            "type_code",
            "content_length",
            "content_type",
            "properties",
            "created_on",
            "expires_on"
        ) VALUES (
            NEW."id",
            NEW."domain",
            NEW."parent_id",
            NEW."name",
            NEW."key",
            NEW."type_code",
            NEW."content_length",
            NEW."content_type",
            NEW."properties",
            NEW."created_on",
            NEW."expires_on"
        );
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD."id" >= 0 THEN
            UPDATE blobs_blobmeta_tbl SET
                "id" = NEW."id",
                "domain" = NEW."domain",
                "parent_id" = NEW."parent_id",
                "name" = NEW."name",
                "key" = NEW."key",
                "type_code" = NEW."type_code",
                "content_length" = NEW."content_length",
                "content_type" = NEW."content_type",
                "properties" = NEW."properties",
                "created_on" = NEW."created_on",
                "expires_on" = NEW."expires_on"
            WHERE OLD."id" >= 0 AND "id" = OLD."id";
        ELSE
            IF NEW.domain != OLD.domain THEN
                RAISE EXCEPTION 'Cannot change domain on attachment metadata';
            ELSIF NEW.type_code != OLD.type_code THEN
                RAISE EXCEPTION 'Cannot change type_code on attachment metadata';
            ELSIF NEW.created_on != OLD.created_on THEN
                RAISE EXCEPTION 'Cannot set created_on on attachment metadata';
            ELSIF NEW.expires_on IS NOT NULL THEN
                RAISE EXCEPTION 'Cannot set expires_on on attachment metadata';
            END IF;

            UPDATE form_processor_xformattachmentsql SET
                "form_id" = NEW."parent_id",
                "name" = NEW."name",
                "blob_id" = NEW."key",
                "blob_bucket" = '',
                "content_length" = NEW."content_length",
                "content_type" = NEW."content_type",
                "properties" = NEW."properties"
            WHERE "id" = -OLD."id";
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD."id" >= 0 THEN
            DELETE FROM blobs_blobmeta_tbl
            WHERE "id" = OLD."id";
        ELSE
            DELETE FROM form_processor_xformattachmentsql
            WHERE "id" = -OLD."id";
        END IF;

        RETURN OLD;
    END IF;

    RETURN NEW;
END; $$ LANGUAGE plpgsql;
