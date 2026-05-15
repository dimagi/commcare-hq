from io import StringIO

from corehq.apps.dump_reload.archive import SimpleSingleStreamWriter


def test_path_is_none():
    writer = SimpleSingleStreamWriter(StringIO())
    assert writer.path is None


def test_open_stream_emits_to_supplied_stream():
    out = StringIO()
    with SimpleSingleStreamWriter(out) as writer:
        with writer.open_stream("sql") as stream:
            stream.write("hello\n")
            stream.meta = {}
    assert out.getvalue() == "hello\n"


def test_does_not_close_underlying_stream_between_dumpers():
    out = StringIO()
    with SimpleSingleStreamWriter(out) as writer:
        for slug in ["a", "b", "c"]:
            with writer.open_stream(slug) as stream:
                stream.write(f"{slug}-data\n")
                stream.meta = {f"{slug}.Model": 1}
    # Underlying stream still writable after the writer exits.
    out.write("after\n")
    text = out.getvalue()
    assert "a-data" in text
    assert "b-data" in text
    assert "c-data" in text
    assert text.endswith("after\n")


def test_meta_round_trips():
    with SimpleSingleStreamWriter(StringIO()) as writer:
        with writer.open_stream("sql") as stream:
            stream.meta = {"auth.User": 5}
        with writer.open_stream("couch") as stream:
            stream.meta = {"users.CommCareUser": 1}
    assert writer.meta == {
        "sql": {"auth.User": 5},
        "couch": {"users.CommCareUser": 1},
    }
