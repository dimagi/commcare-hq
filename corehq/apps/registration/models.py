import datetime
import logging

from django.conf import settings
from django.db import models

from memoized import memoized

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.domain.models import Domain
from corehq.util.quickcache import quickcache

log = logging.getLogger(__name__)


class RegistrationRequest(models.Model):
    tos_confirmed = models.BooleanField(default=False)
    request_time = models.DateTimeField()
    request_ip = models.CharField(max_length=31, null=True)
    activation_guid = models.CharField(max_length=126, unique=True)
    confirm_time = models.DateTimeField(null=True)
    confirm_ip = models.CharField(max_length=31, null=True)
    domain = models.CharField(max_length=255, null=True)
    new_user_username = models.CharField(max_length=255, null=True)
    requesting_user_username = models.CharField(max_length=255, null=True)
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "registration_registrationrequest"

    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)

    @classmethod
    def get_by_guid(cls, guid):
        return RegistrationRequest.objects.filter(activation_guid=guid).first()

    @classmethod
    def get_requests_today(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        return RegistrationRequest.objects.filter(
            request_time__gte=yesterday.isoformat(),
            request_time__lte=today.isoformat(),
        ).count()

    @classmethod
    def get_requests_24hrs_ago(cls):
        today = datetime.datetime.utcnow()
        yesterday = today - datetime.timedelta(1)
        join_on_start = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 0, 0, 0)
        join_on_end = datetime.datetime(
            yesterday.year, yesterday.month, yesterday.day, yesterday.hour, 59, 59, 59)
        requests = RegistrationRequest.objects.filter(
            request_time__gte=join_on_start,
            request_time__lte=join_on_end,
            confirm_time__isnull=True
        )
        return [req for req in requests if req.new_user_username == req.requesting_user_username]

    @classmethod
    def get_request_for_username(cls, username):
        return RegistrationRequest.objects.filter(new_user_username=username).first()


class AsyncSignupRequest(models.Model):
    """
    Use this model to store information from signup or invitation forms when
    the user is redirected to login elsewhere (like SSO) but the signup/invitation
    process must resume when they return.

    NOTE: The reason we use this instead of storing data in request.session
    is that during the SAML handshake for SSO, the Identity Provider
    acknowledges the handshake by posting to a view that is CSRF exempt.
    For security reasons, Django wipes the session data during this process.
    """
    username = models.CharField(max_length=255, db_index=True)
    invitation = models.ForeignKey('users.Invitation', null=True, blank=True, on_delete=models.SET_NULL)
    phone_number = models.CharField(max_length=126, null=True, blank=True)
    project_name = models.CharField(max_length=255, null=True, blank=True)
    atypical_user = models.BooleanField(default=False)
    persona = models.CharField(max_length=128, null=True, blank=True)
    persona_other = models.TextField(null=True, blank=True)
    additional_hubspot_data = models.JSONField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_by_username(cls, username):
        try:
            return cls.objects.get(username=username)
        except cls.MultipleObjectsReturned:
            # this would have to be a weird edge case where an error occurred
            # during the signup process. We should log and then triage.
            log.error(
                f"Fetched multiple AsyncSignupRequests for {username}. "
                f"Please check for errors in any auth backends that might "
                f"be interrupting the sign up workflows."
            )
            return cls.objects.first(username=username)
        except cls.DoesNotExist:
            return None

    @classmethod
    def create_from_registration_form(cls, reg_form, additional_hubspot_data=None):
        """
        Creates an AsyncSignupRequest to store registration form details
        when a user is signing up for an account on HQ and must navigate
        away in the middle of the process
        :param reg_form: RegisterWebUserForm
        :return: AsyncSignupRequest
        """
        username = reg_form.cleaned_data['email']
        async_signup, _ = cls.objects.get_or_create(username=username)

        async_signup.phone_number = reg_form.cleaned_data['phone_number']
        async_signup.project_name = reg_form.cleaned_data['project_name']
        async_signup.atypical_user = reg_form.cleaned_data.get('atypical_user', False)

        # SaaS analytics related
        if settings.IS_SAAS_ENVIRONMENT:
            persona = reg_form.cleaned_data['persona']
            persona_other = reg_form.cleaned_data['persona_other']
            additional_hubspot_data = additional_hubspot_data or {}
            additional_hubspot_data.update({
                'buyer_persona': persona,
                'buyer_persona_other': persona_other,
            })
            async_signup.persona = persona
            async_signup.persona_other = persona_other
            async_signup.additional_hubspot_data = additional_hubspot_data

        async_signup.save()
        return async_signup

    @classmethod
    def create_from_invitation(cls, invitation):
        """
        Creates an AsyncSignupRequest to store invitation details when a user
        is accepting an invitation on HQ and must navigate away in the middle
        of the process to sign in or perform another action
        :param invitation: Invitation
        :return: AsyncSignupRequest
        """
        async_signup, _ = cls.objects.get_or_create(username=invitation.email)
        async_signup.invitation = invitation
        async_signup.save()
        return async_signup

    @classmethod
    def clear_data_for_username(cls, username):
        """
        This makes sure that any outstanding AsyncSignupRequest associated with
        username is deleted.
        :param username: string
        """
        cls.objects.filter(username=username).delete()


class SelfSignupWorkflow(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    initiating_user = models.CharField(max_length=80)
    created_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True)
    subscribed_edition = models.CharField(
        choices=SoftwarePlanEdition.CHOICES,
        max_length=25,
        null=True
    )

    @classmethod
    @quickcache(['domain'], timeout=24 * 60 * 60)
    def get_in_progress_for_domain(cls, domain):
        try:
            workflow = cls.objects.get(
                domain=domain,
                completed_on__isnull=True
            )
            return workflow
        except cls.DoesNotExist:
            return None

    def complete_workflow(self, edition):
        self.completed_on = datetime.datetime.now()
        self.subscribed_edition = edition
        self.save()
        self.get_in_progress_for_domain.clear(self.__class__, self.domain)
