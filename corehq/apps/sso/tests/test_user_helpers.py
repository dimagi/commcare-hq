from testil import eq

from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username


def test_get_email_domain_with_bad_username():
    eq(get_email_domain_from_username('brian@securitytest.io @test.com'), None)


def test_get_email_domain_with_bad_username_strange_characters():
    eq(get_email_domain_from_username('brian@securitytest.com %0a%0c{<@test.com'), None)


def test_get_email_domain_with_bad_username_no_user():
    eq(get_email_domain_from_username('@test.com'), None)


def test_get_email_domain_with_bad_username_multiple_ats():
    eq(get_email_domain_from_username('brian@test.com@bar.com@test.com'), None)


def test_get_email_domain_with_bad_username_spaces():
    eq(get_email_domain_from_username('brian test@test.com'), None)


def test_get_email_domain_with_bad_username_space_at_end():
    eq(get_email_domain_from_username('brian @test.com'), None)


def test_get_email_domain_with_good_username():
    eq(get_email_domain_from_username('foobar123+test@test.com'), 'test.com')
