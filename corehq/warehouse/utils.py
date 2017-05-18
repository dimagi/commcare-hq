from corehq.warehouse.const import DJANGO_MAX_BATCH_SIZE


def django_batch_records(cls, record_iter, field_mapping):
    records = []
    for index, raw_record in enumerate(record_iter):
        record = {}
        for source_key, destination_key in field_mapping:
            record[destination_key] = raw_record.get(source_key)

        records.append(cls(**record))
        if index % DJANGO_MAX_BATCH_SIZE == 0 and index > 0:
            cls.objects.bulk_create(records)
            records = []

    if records:
        cls.objects.bulk_create(records)
