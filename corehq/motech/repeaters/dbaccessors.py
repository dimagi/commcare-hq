from corehq.util.test_utils import unit_testing_only


@unit_testing_only
def delete_all_repeat_records():
    from .models import RepeatRecord
    db = RepeatRecord.get_db()
    results = db.view(
        'repeaters/repeat_records_by_payload_id',
        reduce=False,
        include_docs=True,
    ).all()
    db.bulk_delete([r["doc"] for r in results], empty_on_delete=False)
