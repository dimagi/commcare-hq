from dateutil.parser import parse
from testil import eq

from .. import tinypanda as mod


def test_identity():
    eq(list(mod.TinyPanda(DATA)), DATA)


def test_repr():
    data = mod.TinyPanda(DATA)
    eq(repr(data), f"{repr(DATA[:2])[:-1]}, ... 1 more]")
    eq(repr(mod.TinyPanda(DATA[:2])), repr(DATA[:2]))


def test_len():
    data = mod.TinyPanda(DATA)
    eq(len(data), 3)


def test_repr_select():
    data = mod.TinyPanda(DATA)
    eq(repr(data["a"]), f"[v['a'] for v in {data}]")


def test_get():
    data = mod.TinyPanda(DATA)
    eq(repr(data.get("x")), f"[v.get('x') for v in {data}]")
    eq(list(data.get("x")), [None, None, None])


def test_repr_select_apply_int():
    data = mod.TinyPanda(DATA)
    eq(repr(data["a"].apply(int)), f"[int(v['a']) for v in {data}]")


def test_repr_select_apply_int_lt():
    data = mod.TinyPanda(DATA)
    eq(repr(data["a"].apply(int) < 2), f"[int(v['a']) < 2 for v in {data}]")


def test_select_apply_int_filter():
    data = mod.TinyPanda(DATA)
    eq(list(data[data["a"].apply(int) > 2]), [DATA[2]])


def test_subtract():
    data = mod.TinyPanda(DATA)
    eq(list(data - data[data["a"].apply(int) > 2]), DATA[:2])


def test_filter_by_date():
    data = mod.TinyPanda(DATA)
    d0 = parse(D0)
    print(data["d"].apply(parse) > d0)
    eq(list(data[data["d"].apply(parse) > d0]), DATA[1:])


def test_filter_by_date_and_number():
    data = mod.TinyPanda(DATA)
    d0 = parse(D0)
    where = (data["d"].apply(parse) > d0) & (data["b"].apply(int) < 8)
    eq(repr(where), f"[parse(v['d']) > {d0!r} and int(v['b']) < 8 for v in {data}]")
    eq(list(data[where]), DATA[1:-1])


def test_filter_select_sum():
    data = mod.TinyPanda(DATA)
    where = data["a"].apply(int) < 3
    subset = data[where]
    eq(subset["b"].apply(int).sum(), 6)


D0 = "2020-02-02 20:20:02.02"
D1 = "2020-03-06 20:20:02.02"
D2 = "2020-04-08 20:20:02.02"
DATA = [
    {"a": "1", "b": "2", "d": D0},
    {"a": "2", "b": "4", "d": D1},
    {"a": "3", "b": "8", "d": D2},
]
