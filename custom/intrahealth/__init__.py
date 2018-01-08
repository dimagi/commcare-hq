from __future__ import absolute_import
import six
INTRAHEALTH_DOMAINS = ('ipm-senegal', 'testing-ipm-senegal', 'ct-apr')

OPERATEUR_XMLNSES = (
    'http://openrosa.org/formdesigner/7330597b92db84b1a33c7596bb7b1813502879be',
    'http://openrosa.org/formdesigner/EF8B5DB8-4FB2-4CFB-B0A2-CDD26ADDAE3D'
)

COMMANDE_XMLNSES = (
    'http://openrosa.org/formdesigner/9ED66735-752D-4C69-B9C8-77CEDAAA0348',
    'http://openrosa.org/formdesigner/12b412390011cb9b13406030ab10447ffd99bdf8',
    'http://openrosa.org/formdesigner/865DDF78-90D7-4B7C-B3A5-9D7F530B471D'
)

RAPTURE_XMLNSES = (
    'http://openrosa.org/formdesigner/AD88DE3E-6AFC-48A5-8BEC-092419C1D45A',
)

LIVRAISON_XMLNSES = ("http://openrosa.org/formdesigner/182649A1-A3BB-4F56-988C-2C103DBAA6D7", )

RECOUVREMENT_XMLNSES = ('http://openrosa.org/formdesigner/61478ca7d20e8e1fa2fd110b1b2b4d46bb5b6b9c',
                        'http://openrosa.org/formdesigner/c03317d26979ba4b656fac23ef1f03dfe4337b1d')

_PRODUCT_NAMES = {
    u'diu': [u"diu"],
    u'jadelle': [u"jadelle"],
    u'depo-provera': [u"d\xe9po-provera", u"depo-provera"],
    u'microlut/ovrette': [u"microlut/ovrette"],
    u'microgynon/lof.': [u"microgynon/lof."],
    u'preservatif masculin': [u"pr\xe9servatif masculin", u"preservatif masculin", u"preservatif_masculin"],
    u'preservatif feminin': [u"pr\xe9servatif f\xe9minin", u"preservatif feminin", u"preservatif_feminin"],
    u'cu': [u"cu"],
    u'collier': [u"collier"]
}

PRODUCT_NAMES = {v: k for k, values in six.iteritems(_PRODUCT_NAMES) for v in values}

PRODUCT_MAPPING = {
    "collier": "Collier",
    "cu": "CU",
    "depoprovera": "Depo-Provera",
    "diu": "DIU",
    "jadelle": "Jadelle",
    "microgynon": "Microgynon/Lof.",
    "microlut": "Microlut/Ovrette",
    "preservatif_feminin": "Preservatif Feminin",
    "preservatif_masculin": "Preservatif Masculin",
    "sayana_press": "Sayana Press",
    "implanon": "IMPLANON"
}
