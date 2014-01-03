import json

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponseRedirect, HttpResponse
from django.template import Context, Template
from django.utils.decorators import method_decorator
from django.views.generic import FormView

from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.views import BaseAdminCRUDFormView
from corehq.apps.domain.decorators import require_superuser


@require_superuser
def default_announcement(request):
    from corehq.apps.announcements.interface import ManageGlobalHQAnnouncementsInterface
    return HttpResponseRedirect(ManageGlobalHQAnnouncementsInterface.get_url())

class AnnouncementAdminCRUDFormView(BaseAdminCRUDFormView):
    base_loc = "corehq.apps.announcements.forms"


@login_required()
def clear_announcement(request, announcement_id):
    if request.couch_user:
        try:
            announcement = HQAnnouncement.get(announcement_id)
            request.couch_user.announcements_seen.append(announcement._id)
            request.couch_user.save()
            return HttpResponse("cleared")
        except Exception as e:
            HttpResponse("Problem clearing announcement: %s" % e)
    return HttpResponse("not cleared")


class EmailsField(forms.CharField):
    widget = forms.Textarea

    def to_python(self, value):
        if not value:
            return []
        return [email.strip() for email in value.split(',')]


class EmailForm(forms.Form):
    to = EmailsField(required=False)
    reply_to = EmailsField(required=False)
    cc = EmailsField(required=False)
    subject = forms.CharField(required=False, widget=forms.Textarea)
    message = forms.CharField(required=False, widget=forms.Textarea)
    context = forms.CharField(required=False, widget=forms.Textarea)

    def clean_context(self):
        raw = self.cleaned_data['context']
        if not raw:
            return {}
        try:
            context = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("The context is not valid JSON")
        if not isinstance(context, list):
            raise forms.ValidationError(
                "The context should be a list, one per email")
        return context

    def clean_reply_to(self):
        reply = self.cleaned_data['reply_to'] or [settings.SERVER_EMAIL]
        if len(reply) > 1:
            raise forms.ValidationError(
                "You can only specify one 'reply_to' address")
        return reply[0]


class TemplatedEmailer(FormView):
    template_name = 'announcements/emailer.html'
    form_class = EmailForm

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(TemplatedEmailer, self).dispatch(*args, **kwargs)

    def make_email(self, context):
        to = context.get('to', self.to)
        to = to if isinstance(to, list) else [to]
        cc = context.get('cc', self.cc)
        cc = cc if isinstance(cc, list) else [cc]
        return {
            'message': self.message.render(Context(context)),
            'subject': self.subject.render(Context(context)),
            'recipients': to + cc,
            'reply_to': context.get('reply_to', self.reply_to), 
        }

    def form_valid(self, form):
        self.message = Template(form.cleaned_data['message'])
        self.subject = Template(form.cleaned_data['subject'])

        self.to = form.cleaned_data['to']
        self.reply_to = form.cleaned_data['reply_to']
        self.cc = form.cleaned_data['cc']

        self.emails = []
        if not form.cleaned_data['context']:
            self.emails.append(self.make_email({}))
        else:
            for context in form.cleaned_data['context']:
                self.emails.append(self.make_email(context))

        if self.request.POST.get('send', None):
            return self.send_emails(form)
        return self.render_to_response(self.get_context_data(
            form=form,
            emails=self.emails,
        ))

    def send_emails(self, form):
        errors = []
        for email in self.emails:
            try:
                send_mail(
                    email['subject'],
                    email['message'],
                    email['reply_to'],
                    email['recipients'],
                )
            except Exception, e:
                errors.append({
                    'to': email['recipients'],
                    'message': e,
                })
        if errors:
            return self.render_to_response(self.get_context_data(
                form=form,
                mailing_errors=errors,
            ))
        return HttpResponse("Messages sent")

