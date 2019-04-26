CREATE FUNCTION copy_balance() RETURNS trigger AS $copy_balance$
    BEGIN
        NEW.new_updated_balance = NEW.updated_balance;
        RETURN NEW;
    END;
$copy_balance$ LANGUAGE plpgsql;

CREATE TRIGGER copy_balance_trigger BEFORE INSERT OR UPDATE ON form_processor_ledgertransaction
    FOR EACH ROW EXECUTE PROCEDURE copy_balance();
