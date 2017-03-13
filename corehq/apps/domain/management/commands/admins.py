from django.core.management.base import LabelCommand
import operator
from dimagi.utils.couch.database import get_db

doms = [
"corpora",
"rx",
"example",
"rxehegdm",
"mira-round-1trial",
"anova",
"bihar",
"malnutrition-project",
"tns-tutuwa",
"vecna",
"rct-refuse-collection",
"kawok-malaria",
"wag-chelsea-sw",
"cyclonepostmonitoring",
"commsell",
"acf",
"testing-sj",
"ekjut",
"chrosam-study",
"mvp-va",
"finesession",
"nutritionmeast",
"baobab",
"crs-remind",
"sheel-test",
"sapanatest",
"mikesproject",
"wvindia",
"tribentriallao",
"opm",
"oneacre",
"nyu-corrections-study",
"mvp-sauri",
"ian-test-project",
"china",
"union-jharkhand",
"tulasalud",
"followup-first-mira",
"drew",
"wits-ca",
"rmf",
"onboarding-test-space",
"india-fm-position",
"hsph-dev",
"hsph-betterbirth-pilot-2",
"healthinfo",
"gsid",
"bombay-workshop-demo",
"yedispace",
"tc-test",
"pradan-mis-dev",
"mikescommconnectdomain",
"kawok",
"ekam",
"yonsei-emco",
"whptest",
"wagchelsea",
"tns-sa",
"tfwdemo",
"test-soukya",
"pathfinder",
"pact",
"mvp-pampaida",
"monitoring",
"mchip-haryana",
"lucawork",
"lla-pilot",
"jonstest",
"jeremytraining",
"jamestest1",
"itech-rmp",
"dmoz-demo-commconnect",
"demoform",
"crs-mip",
"asdprom",
"uip-and-mnh",
"sneha-div2-poc",
"sef",
"rxehelive",
"pathways-india-mis",
"mycadre",
"moz-gmp-nutrition",
"mob-test",
"mattstestproject",
"maternityissues",
"lao-livelihoods-test",
"ibex",
"hiv-project-namc",
"gc",
"esoergel",
"emergency",
"demo-lesotho-icap-tb-ppp",
"cmmhr",
"benin",
"aprateektest",
"ag-demos",
"Missing field",
"Other values",
]


def admins(domain):
    return domain, filter(None, [u["doc"].get('email', "<no email found>") for u in get_db().view('users/admins_by_domain', key=domain, reduce=False, include_docs=True)])
    # print get_db().view('users/admins_by_domain', key=domain).all()

class Command(LabelCommand):

    def handle(self, *args, **options):
        admin_mapping = dict([admins(dom) for dom in doms])
        import pprint
        pp = pprint.PrettyPrinter(indent=2)
        pp.pprint(admin_mapping)

        print "all users"
        users = set(reduce(operator.add, admin_mapping.values()))
        pp.pprint(users)

        print "all users minus dimagi"
        pp.pprint(filter(lambda e: not e.endswith('@dimagi.com'), users))