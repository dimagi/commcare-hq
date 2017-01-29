-- Table: Child Categories
DROP TABLE IF EXISTS child_health_categories;
CREATE TABLE child_health_categories
(
	gender text NOT NULL,
	age_tranche text NOT NULL,
	caste text NOT NULL,
	disabled text NOT NULL,
	minority text NOT NULL,
	resident text NOT NULL
);
CREATE INDEX child_health_categories_indx1 ON child_health_categories (gender, age_tranche, caste, disabled, minority, resident);

INSERT INTO child_health_categories (
    SELECT
        "gender"."column1" as "gender",
        "age_tranche"."column1" as "age_tranche",
        "caste"."column1" as "caste",
        "disabled"."column1" as "disabled",
        "minority"."column1" as "minority",
        "resident"."column1" as "resident"
    FROM
        (VALUES ('M'), ('F')) "gender"
    CROSS JOIN
        (VALUES ('0'), ('6'), ('12'), ('24'), ('36'), ('48'), ('60'), ('72')) "age_tranche"
    CROSS JOIN
        (VALUES ('st'), ('sc'), ('obc'), ('other')) "caste"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "disabled"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "minority"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "resident"
);

-- Table: CCS Record Categories
DROP TABLE IF EXISTS ccs_record_categories;
CREATE TABLE ccs_record_categories
(
	ccs_status text NOT NULL,
	trimester text,
	caste text NOT NULL,
	disabled text NOT NULL,
	minority text NOT NULL,
	resident text NOT NULL
);
CREATE INDEX ccs_record_categories_indx1 ON ccs_record_categories (ccs_status, trimester, caste, disabled, minority, resident);

INSERT INTO ccs_record_categories (
    SELECT
        "record_type"."column1" as "ccs_status",
        "record_type"."column2" as "trimester",
        "caste"."column1" as "caste",
        "disabled"."column1" as "disabled",
        "minority"."column1" as "minority",
        "resident"."column1" as "resident"
    FROM
        (VALUES ('pregnant', '1'), ('pregnant', '2'), ('pregnant', '3'), ('lactating', '')) "record_type"
    CROSS JOIN
        (VALUES ('st'), ('sc'), ('obc'), ('other')) "caste"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "disabled"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "minority"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "resident"
);

-- Table: THR Categories
DROP TABLE IF EXISTS thr_categories;
CREATE TABLE thr_categories
(
	beneficiary_type text NOT NULL,
	caste text NOT NULL,
	disabled text NOT NULL,
	minority text NOT NULL,
	resident text NOT NULL
);
CREATE INDEX thr_categories_indx1 ON thr_categories (beneficiary_type, caste, disabled, minority, resident);

INSERT INTO thr_categories (
    SELECT
        "beneficiary_type"."column1" as "beneficiary_type",
        "caste"."column1" as "caste",
        "disabled"."column1" as "disabled",
        "minority"."column1" as "minority",
        "resident"."column1" as "resident"
    FROM
        (VALUES ('pregnant'), ('lactating'), ('child')) "beneficiary_type"
    CROSS JOIN
        (VALUES ('st'), ('sc'), ('obc'), ('other')) "caste"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "disabled"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "minority"
    CROSS JOIN
        (VALUES ('yes'), ('no')) "resident"
);
