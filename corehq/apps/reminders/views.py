from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq import privileges
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.reminders.forms import NO_RESPONSE, KeywordForm
from corehq.apps.reminders.util import get_combined_id, split_combined_id
from corehq.apps.sms.models import Keyword, KeywordAction
from corehq.apps.sms.views import BaseMessagingSectionView


class AddStructuredKeywordView(BaseMessagingSectionView):
    urlname = 'add_structured_keyword'
    page_title = gettext_noop("New Structured Keyword")
    template_name = 'reminders/keyword.html'
    process_structured_message = True

    @method_decorator(requires_privilege_with_fallback(privileges.INBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(AddStructuredKeywordView, self).dispatch(*args, **kwargs)

    @property
    def parent_pages(self):
        return [
            {
                'title': KeywordsListView.page_title,
                'url': reverse(KeywordsListView.urlname, args=[self.domain]),
            },
        ]

    @property
    @memoized
    def keyword(self):
        return Keyword(domain=self.domain)

    @property
    def page_context(self):
        return {
            'form': self.keyword_form,
        }

    @property
    @memoized
    def keyword_form(self):
        if self.request.method == 'POST':
            return KeywordForm(
                self.request.POST,
                domain=self.domain,
                process_structured=self.process_structured_message,
            )
        return KeywordForm(
            domain=self.domain,
            process_structured=self.process_structured_message,
        )

    def post(self, request, *args, **kwargs):
        if self.keyword_form.is_valid():
            with transaction.atomic():
                self.keyword.keyword = self.keyword_form.cleaned_data['keyword']
                self.keyword.description = self.keyword_form.cleaned_data['description']
                self.keyword.delimiter = self.keyword_form.cleaned_data['delimiter']
                self.keyword.override_open_sessions = self.keyword_form.cleaned_data['override_open_sessions']

                self.keyword.initiator_doc_type_filter = []
                if self.keyword_form.cleaned_data['allow_keyword_use_by'] == 'users':
                    self.keyword.initiator_doc_type_filter.append('CommCareUser')
                if self.keyword_form.cleaned_data['allow_keyword_use_by'] == 'cases':
                    self.keyword.initiator_doc_type_filter.append('CommCareCase')

                self.keyword.save()

                self.keyword.keywordaction_set.all().delete()
                if self.keyword_form.cleaned_data['sender_content_type'] != NO_RESPONSE:
                    app_id, form_unique_id = split_combined_id(
                        self.keyword_form.cleaned_data['sender_app_and_form_unique_id']
                    )
                    self.keyword.keywordaction_set.create(
                        recipient=KeywordAction.RECIPIENT_SENDER,
                        action=self.keyword_form.cleaned_data['sender_content_type'],
                        message_content=self.keyword_form.cleaned_data['sender_message'],
                        app_id=app_id,
                        form_unique_id=form_unique_id,
                    )
                if self.process_structured_message:
                    app_id, form_unique_id = split_combined_id(
                        self.keyword_form.cleaned_data['structured_sms_app_and_form_unique_id']
                    )
                    self.keyword.keywordaction_set.create(
                        recipient=KeywordAction.RECIPIENT_SENDER,
                        action=KeywordAction.ACTION_STRUCTURED_SMS,
                        app_id=app_id,
                        form_unique_id=form_unique_id,
                        use_named_args=self.keyword_form.cleaned_data['use_named_args'],
                        named_args=self.keyword_form.cleaned_data['named_args'],
                        named_args_separator=self.keyword_form.cleaned_data['named_args_separator'],
                    )
                if self.keyword_form.cleaned_data['other_recipient_content_type'] != NO_RESPONSE:
                    app_id, form_unique_id = split_combined_id(
                        self.keyword_form.cleaned_data['other_recipient_app_and_form_unique_id']
                    )
                    self.keyword.keywordaction_set.create(
                        recipient=self.keyword_form.cleaned_data['other_recipient_type'],
                        recipient_id=self.keyword_form.cleaned_data['other_recipient_id'],
                        action=self.keyword_form.cleaned_data['other_recipient_content_type'],
                        message_content=self.keyword_form.cleaned_data['other_recipient_message'],
                        app_id=app_id,
                        form_unique_id=form_unique_id,
                    )

                return HttpResponseRedirect(reverse(KeywordsListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class AddNormalKeywordView(AddStructuredKeywordView):
    urlname = 'add_normal_keyword'
    page_title = gettext_noop("New Keyword")
    process_structured_message = False


class EditStructuredKeywordView(AddStructuredKeywordView):
    urlname = 'edit_structured_keyword'
    page_title = gettext_noop("Edit Structured Keyword")
    readonly = False

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.keyword_id])

    @property
    def keyword_id(self):
        return self.kwargs.get('keyword_id')

    @property
    @memoized
    def keyword(self):
        if not self.keyword_id:
            raise Http404()

        try:
            k = Keyword.objects.get(couch_id=self.keyword_id)
        except Keyword.DoesNotExist:
            raise Http404()

        if k.domain != self.domain:
            raise Http404()

        return k

    @property
    @memoized
    def keyword_form(self):
        initial = self.get_initial_values()
        if self.request.method == 'POST':
            form = KeywordForm(
                self.request.POST,
                domain=self.domain,
                initial=initial,
                keyword_id=self.keyword_id,
                process_structured=self.process_structured_message,
                readonly=self.readonly,
            )
            form._sk_id = self.keyword_id
            return form
        return KeywordForm(
            domain=self.domain,
            initial=initial,
            process_structured=self.process_structured_message,
            readonly=self.readonly,
        )

    def can_view_data(self, request):
        if self.readonly:
            return True

        if self.keyword.upstream_id:
            return request.couch_user.can_edit_linked_data(self.domain)

        return True

    def get(self, request, *args, **kwargs):
        if not self.can_view_data(request):
            raise PermissionDenied
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.can_view_data(request):
            raise PermissionDenied
        return super().post(request, *args, **kwargs)

    def get_initial_values(self):
        initial = {
            'keyword': self.keyword.keyword,
            'description': self.keyword.description,
            'delimiter': self.keyword.delimiter,
            'override_open_sessions': self.keyword.override_open_sessions,
            'sender_content_type': NO_RESPONSE,
        }
        is_case_filter = "CommCareCase" in self.keyword.initiator_doc_type_filter
        is_user_filter = "CommCareUser" in self.keyword.initiator_doc_type_filter
        if is_case_filter and not is_user_filter:
            initial.update({
                'allow_keyword_use_by': 'cases',
            })
        elif is_user_filter and not is_case_filter:
            initial.update({
                'allow_keyword_use_by': 'users',
            })
        for action in self.keyword.keywordaction_set.all():
            if action.action == KeywordAction.ACTION_STRUCTURED_SMS:
                if self.process_structured_message:
                    initial.update({
                        'structured_sms_app_and_form_unique_id': get_combined_id(action.app_id,
                                                                                 action.form_unique_id),
                        'use_custom_delimiter': self.keyword.delimiter is not None,
                        'use_named_args_separator': action.named_args_separator is not None,
                        'use_named_args': action.use_named_args,
                        'named_args_separator': action.named_args_separator,
                        'named_args': [{"name": k, "xpath": v} for k, v in action.named_args.items()],
                    })
            elif action.recipient == KeywordAction.RECIPIENT_SENDER:
                initial.update({
                    'sender_content_type': action.action,
                    'sender_message': action.message_content,
                    'sender_app_and_form_unique_id': get_combined_id(action.app_id, action.form_unique_id),
                })
            else:
                initial.update({
                    'other_recipient_type': action.recipient,
                    'other_recipient_id': action.recipient_id,
                    'other_recipient_content_type': action.action,
                    'other_recipient_message': action.message_content,
                    'other_recipient_app_and_form_unique_id': get_combined_id(action.app_id,
                                                                              action.form_unique_id),
                })
        return initial


class EditNormalKeywordView(EditStructuredKeywordView):
    urlname = 'edit_normal_keyword'
    page_title = gettext_noop("Edit Normal Keyword")
    process_structured_message = False

    @property
    @memoized
    def keyword(self):
        k = super(EditNormalKeywordView, self).keyword
        # don't allow structured keywords to be edited in this view.
        if k.is_structured_sms():
            raise Http404()

        return k


class ViewStructuredKeywordView(EditStructuredKeywordView):
    urlname = 'view_structured_keyword'
    readonly = True


class ViewNormalKeywordView(EditNormalKeywordView):
    urlname = 'view_normal_keyword'
    readonly = True


class KeywordsListView(BaseMessagingSectionView, CRUDPaginatedViewMixin):
    template_name = 'reminders/keyword_list.html'
    urlname = 'keyword_list'
    page_title = gettext_noop("Keywords")

    limit_text = gettext_noop("keywords per page")
    empty_notification = gettext_noop("You have no keywords. Please add one!")
    loading_message = gettext_noop("Loading keywords...")

    @use_multiselect
    @method_decorator(requires_privilege_with_fallback(privileges.INBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(KeywordsListView, self).dispatch(*args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def total(self):
        return Keyword.get_by_domain(self.domain).count()

    @property
    def column_names(self):
        columns = [
            _("Keyword"),
            _("Description"),
            _("Action"),
        ]

        if self.has_linked_data():
            columns.append("")  # Upstream ID column has no header

        return columns

    def has_linked_data(self):
        return any((keyword.upstream_id for keyword in self._all_keywords()))

    def can_edit_linked_data(self):
        return self.request.couch_user.can_edit_linked_data(self.domain)

    @property
    def page_context(self):
        context = self.pagination_context
        context['has_linked_data'] = self.has_linked_data()
        context['can_edit_linked_data'] = self.can_edit_linked_data()
        return context

    @memoized
    def _all_keywords(self):
        return Keyword.get_by_domain(self.domain)

    @property
    def paginated_list(self):
        for keyword in self._all_keywords()[self.skip:self.skip + self.limit]:
            yield {
                'itemData': self._fmt_keyword_data(keyword),
                'template': 'keyword-row-template',
            }

    def _fmt_keyword_data(self, keyword):
        return {
            'id': keyword.couch_id,
            'keyword': keyword.keyword,
            'description': keyword.description,
            'upstream_id': keyword.upstream_id,
            'viewUrl': reverse(
                ViewStructuredKeywordView.urlname,
                args=[self.domain, keyword.couch_id]
            ) if keyword.is_structured_sms() else reverse(
                ViewNormalKeywordView.urlname,
                args=[self.domain, keyword.couch_id]
            ),
            'editUrl': reverse(
                EditStructuredKeywordView.urlname,
                args=[self.domain, keyword.couch_id]
            ) if keyword.is_structured_sms() else reverse(
                EditNormalKeywordView.urlname,
                args=[self.domain, keyword.couch_id]
            ),
            'deleteModalId': 'delete-%s' % keyword.couch_id,
        }

    def _fmt_deleted_keyword_data(self, keyword):
        return {
            'keyword': keyword.keyword,
            'description': keyword.description,
        }

    def get_deleted_item_data(self, item_id):
        try:
            k = Keyword.objects.get(couch_id=item_id)
        except Keyword.DoesNotExist:
            raise Http404()

        if k.domain != self.domain:
            raise Http404()

        k.delete()

        return {
            'itemData': self._fmt_deleted_keyword_data(k),
            'template': 'keyword-deleted-template',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response
