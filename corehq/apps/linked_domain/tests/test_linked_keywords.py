from corehq.apps.linked_domain.keywords import create_linked_keyword, update_keyword
from corehq.apps.app_manager.models import Module
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.reminders.models import METHOD_SMS
from corehq.apps.sms.models import Keyword, KeywordAction


class TestLinkedKeywords(BaseLinkedAppsTest):
    def setUp(self):
        super(TestLinkedKeywords, self).setUp()

        module = self.master1.add_module(Module.new_module("M1", None))
        master_form = module.new_form("f1", None, self.get_xml("very_simple_form").decode("utf-8"))
        self.keyword = Keyword(
            domain=self.domain_link.master_domain,
            keyword="ping",
            description="The description",
            override_open_sessions=True,
        )
        self.keyword.save()
        self.keyword.keywordaction_set.create(
            recipient=KeywordAction.RECIPIENT_SENDER,
            action=METHOD_SMS,
            message_content="pong",
            app_id=self.master1.get_id,
            form_unique_id=master_form.unique_id,
        )

    def tearDown(self):
        self.keyword.delete()
        super(TestLinkedKeywords, self).tearDown()

    def test_create_keyword_link(self):
        new_keyword_id = create_linked_keyword(self.domain_link, self.keyword.id)
        new_keyword = Keyword.objects.get(id=new_keyword_id)
        self.assertEqual(new_keyword.keyword, self.keyword.keyword)

        new_keyword_action = new_keyword.keywordaction_set.first()
        self.assertEqual(
            new_keyword_action.message_content,
            self.keyword.keywordaction_set.first().message_content,
        )

        self.assertEqual(new_keyword_action.app_id, self.linked_app.get_id)

    def test_update_keyword_link(self):
        new_keyword_id = create_linked_keyword(self.domain_link, self.keyword.id)
        self.keyword.keyword = "foo"
        self.keyword.save()
        keyword_action = self.keyword.keywordaction_set.first()
        keyword_action.message_content = "bar"
        keyword_action.save()

        update_keyword(self.domain_link, new_keyword_id)

        linked_keyword = Keyword.objects.get(id=new_keyword_id)
        self.assertEqual(linked_keyword.keyword, "foo")
        self.assertEqual(linked_keyword.keywordaction_set.first().message_content, "bar")
