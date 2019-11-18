-- Ensure new and updated values are applied to both columns
CREATE FUNCTION copy_delta() RETURNS trigger AS $copy_delta$
    BEGIN
        NEW.new_delta = NEW.delta;
        RETURN NEW;
    END;
$copy_delta$ LANGUAGE plpgsql;

CREATE TRIGGER copy_delta_trigger BEFORE INSERT OR UPDATE ON form_processor_ledgertransaction
    FOR EACH ROW EXECUTE PROCEDURE copy_delta();
