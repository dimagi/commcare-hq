from functools import singledispatch

from couchdbkit.ext.django.schema import DictProperty, Document
from django.test import SimpleTestCase
from typing_extensions import TypedDict


class Spam(TypedDict):
    ham: str
    eggs: int
    spam: list


class SpamDoc(Document):
    spam = DictProperty()


@singledispatch
def get_breakfast(dict_):
    return type(dict_)


@get_breakfast.register(Spam)
def get_spam(dict_: Spam):
    return dict_["spam"]


@get_breakfast.register(TypedDict)
def get_eggs(dict_: TypedDict):
    return dict_["eggs"]


class TypedDictTests(SimpleTestCase):

    def setUp(self):
        self.spam = Spam(
            ham="eggs",
            eggs=2,
            spam=["spam", "spam", "spam"],
        )

    def test_document_definition(self):
        SpamDoc.wrap({
            "spam": self.spam
        })

    def test_singledispatch(self):
        result = get_breakfast(self.spam)
        self.assertEqual(result, ["spam", "spam", "spam"])
