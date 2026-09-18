from unittest import mock

from django.test import Client
from django.urls import reverse

from unmagic import use

from dimagi.utils.web import get_url_base

from corehq.apps.short_links.models import ShortLink

DOMAIN = 'short-links-domain'
TARGET = 'https://www.commcarehq.org/webforms/abc/def/'


def _code(short_url):
    return short_url.rsplit('/', 1)[-1]


def _follow(short_url):
    return Client().get(reverse('follow_short_link', args=[_code(short_url)]))


@use('db')
def test_shorten_returns_an_absolute_url_carrying_the_code():
    short_url = ShortLink.objects.get_or_create_for_url(DOMAIN, TARGET).short_url

    code = ShortLink.objects.get(target_url=TARGET).code
    assert short_url == f'{get_url_base()}/s/{code}'


@use('db')
def test_a_code_that_collides_is_generated_again():
    taken = ShortLink.objects.create(domain=DOMAIN, target_url='https://example.org/')
    codes = iter([taken.code, 'zzzzzzzzzzzz'])

    with mock.patch.object(
        ShortLink._meta.get_field('code'), '_get_default', lambda: next(codes)
    ):
        link = ShortLink.objects.get_or_create_for_url(DOMAIN, TARGET)

    assert link.code == 'zzzzzzzzzzzz'


@use('db')
def test_following_a_short_link_redirects_to_its_target():
    response = _follow(ShortLink.objects.get_or_create_for_url(DOMAIN, TARGET).short_url)

    assert response.status_code == 301
    assert response.url == TARGET


@use('db')
def test_an_unknown_code_is_not_found():
    assert _follow('/s/9BvKq2mXtZaF').status_code == 404


@use('db')
def test_shortening_the_same_target_twice_reuses_the_code():
    assert ShortLink.objects.get_or_create_for_url(
        DOMAIN, TARGET
    ) == ShortLink.objects.get_or_create_for_url(DOMAIN, TARGET)


@use('db')
def test_a_code_is_not_reused_across_domains():
    assert ShortLink.objects.get_or_create_for_url(
        DOMAIN, TARGET
    ) != ShortLink.objects.get_or_create_for_url('another-domain', TARGET)
