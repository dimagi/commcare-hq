from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.cache import caches

from corehq.apps.accounting.models import Subscription
from corehq.util.quickcache import quickcache


def test_py2to3_caching():
    @quickcache([])
    def get_value():
        raise Exception("should not get here")

    py2_pickle = (
        b'\x80\x02cdjango.db.models.base\nmodel_unpickle\nq\x01X\n\x00\x00\x00'
        b'accountingq\x02U\x0cSubscriptionq\x03\x86\x85Rq\x04}q\x05(U\x14do_no'
        b't_email_invoiceq\x06\x89U\rsubscriber_idq\x07K\x01U\x08date_endq\x08'
        b'NU\x15auto_generate_creditsq\t\x89U\x06_stateq\ncdjango.db.models.ba'
        b'se\nModelState\nq\x0b)\x81q\x0c}q\r(U\x06addingq\x0e\x89U\x02dbq\x0f'
        b'X\x07\x00\x00\x00defaultq\x10ubU\x0efunding_sourceq\x11X\x06\x00\x00'
        b'\x00CLIENTU\x02idq\x12K\rU\x0edo_not_invoiceq\x13\x88U\x13skip_auto_'
        b'downgradeq\x14\x89U\x11no_invoice_reasonq\x15X\x00\x00\x00\x00U\ndat'
        b'e_startq\x16cdatetime\ndate\nq\x17U\x04\x07\xe3\x03\x19\x85Rq\x18U'
        b'\x16salesforce_contract_idq\x19X\x00\x00\x00\x00U\x1askip_auto_downg'
        b'rade_reasonq\x1aX\x00\x00\x00\x00U\x0cservice_typeq\x1bX\x07\x00\x00'
        b'\x00PRODUCTU\x10is_hidden_to_opsq\x1c\x89U\x13_plan_version_cacheq'
        b'\x1dh\x01X\n\x00\x00\x00accountingq\x1eU\x13SoftwarePlanVersionq\x1f'
        b'\x86\x85Rq }q!(U\x0fproduct_rate_idq"K\x0bU\x0b_role_cacheq#h\x01X'
        b"\x0c\x00\x00\x00django_prbacq$U\x04Roleq%\x86\x85Rq&}q'(U\x0bdescrip"
        b'tionq(X\x00\x00\x00\x00U\nparametersq)c__builtin__\nset\nq*]\x85Rq+U'
        b'\x0f_django_versionq,U\x071.11.20h\nh\x0b)\x81q-}q.(h\x0e\x89h\x0fh'
        b'\x10ubU\x04slugq/X\x10\x00\x00\x00standard_plan_v0h\x12K&U\x04nameq0'
        b'X\r\x00\x00\x00Standard PlanubU\x07plan_idq1K\nh,U\x071.11.20h\nh'
        b'\x0b)\x81q2}q3(h\x0e\x89h\x0fh\x10ubU\tis_activeq4\x88U\x07role_idq5'
        b'K&U\rlast_modifiedq6cdatetime\ndatetime\nq7U\n\x07\xe2\n\x17\x01"'
        b'\x07\t^\xdb\x85Rq8U\x0cdate_createdq9h7U\n\x07\xe2\n\x17\x01"\x07\t9'
        b'\xa8\x85Rq:h\x12K\x0bubU\naccount_idq;K\x04h4\x88U$skip_invoicing_if'
        b'_no_feature_chargesq<\x89U\x0fpro_bono_statusq=X\n\x00\x00\x00FULL_P'
        b'RICEh6h7U\n\x07\xe3\x03\x19\x15\x1a\x0e\x02\xf1\x9e\x85Rq>h,U\x071.1'
        b'1.20U\x0fplan_version_idq?K\x0bU\x15do_not_email_reminderq@\x89U\x08'
        b'is_trialqA\x89h9h7U\n\x07\xe3\x03\x19\x15\x1a\x0e\x02\xf1\x00\x85RqB'
        b'ub.'
    )

    cache = caches['redis'].client
    quickcache_key = get_value.get_cache_key()
    redis_key = cache.make_key(quickcache_key)
    redis = cache.get_client()
    redis.set(redis_key, py2_pickle, px=3000)

    value = get_value()
    assert isinstance(value, Subscription), repr(value)
