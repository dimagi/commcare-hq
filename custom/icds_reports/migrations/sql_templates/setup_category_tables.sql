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
