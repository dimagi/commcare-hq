
def django_batch_records(cls, record_iter, field_mapping):
    records = []
    for raw_record in record_iter:
        record = {}
        for source_key, destination_key in field_mapping:
            record[destination_key] = raw_record.get(source_key)

        records.append(cls(**record))
    cls.objects.bulk_create(records)
