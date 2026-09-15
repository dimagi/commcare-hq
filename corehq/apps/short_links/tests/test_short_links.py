from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

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
    short_url = ShortLink.shorten(DOMAIN, TARGET).short_url

    code = ShortLink.objects.get(target_url=TARGET).code
    assert short_url == f'{get_url_base()}/s/{code}'


@use('db')
def test_following_a_short_link_redirects_to_its_target():
    response = _follow(ShortLink.shorten(DOMAIN, TARGET).short_url)

    # temporary, so that nothing caches a code whose target may stop working
    assert response.status_code == 302
    assert response.url == TARGET


@use('db')
def test_an_unknown_code_is_not_found():
    assert _follow('/s/9BvKq2mXtZaF').status_code == 404


@use('db')
def test_an_expired_code_is_not_found():
    link = ShortLink.objects.create(
        domain=DOMAIN,
        target_url=TARGET,
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    assert _follow(link.short_url).status_code == 404


@use('db')
def test_shortening_the_same_target_twice_reuses_the_code():
    assert ShortLink.shorten(DOMAIN, TARGET) == ShortLink.shorten(DOMAIN, TARGET)


@use('db')
def test_a_code_is_not_reused_across_domains():
    assert ShortLink.shorten(DOMAIN, TARGET) != ShortLink.shorten('another-domain', TARGET)


@use('db')
def test_a_code_is_reused_only_while_it_outlasts_what_the_caller_needs():
    in_an_hour = timezone.now() + timedelta(hours=1)
    hour_long = ShortLink.shorten(DOMAIN, TARGET, expires_at=in_an_hour)

    assert ShortLink.shorten(
        DOMAIN, TARGET, expires_at=in_an_hour - timedelta(minutes=1)
    ) == hour_long
    assert ShortLink.shorten(
        DOMAIN, TARGET, expires_at=in_an_hour + timedelta(minutes=1)
    ) != hour_long


@use('db')
def test_a_code_that_never_expires_is_reused_for_any_lifespan():
    permanent = ShortLink.shorten(DOMAIN, TARGET)

    assert ShortLink.shorten(
        DOMAIN, TARGET, expires_at=timezone.now() + timedelta(days=1)
    ) == permanent


@use('db')
def test_an_expiring_code_is_not_reused_for_a_link_that_must_not_expire():
    expiring = ShortLink.shorten(DOMAIN, TARGET, expires_at=timezone.now() + timedelta(days=1))

    assert ShortLink.shorten(DOMAIN, TARGET) != expiring
