from django.db.models.signals import post_save
from django.core.mail import send_mail
import settings
from models import LogTrack
from django.template.loader import render_to_string

from django.core.mail.message import EmailMessage
from django.core.mail import SMTPConnection


def sendAlert(sender, instance, created, *args, **kwargs): #get sender, instance, created    
    # only send emails on newly created logs, not all of them
    if not created:
        return     
    #set a global threshold to say if anything is a logging.ERROR, chances are
    #we always want an alert.
    if instance.level >= settings.LOGTRACKER_ALERT_THRESHOLD:                    
        context = {}
        context['log'] = instance    
        rendered_text = render_to_string("logtracker/alert_display.html", context)
        # Send it to an email address baked into the settings/ini file.
        # restrict the subject to 78 characters to comply with the RFC
        title = ("[Log Tracker] " + instance.message)[:78]
        # newlines makey title mad        
        title = title.replace("\n", ",")
        
        conn = SMTPConnection(username=settings.EMAIL_LOGIN,
                                   port=settings.EMAIL_SMTP_PORT,
                                   host=settings.EMAIL_SMTP_HOST,
                                   password=settings.EMAIL_PASSWORD,
                                   use_tls=True,
                                   fail_silently=False)
        
        msg = EmailMessage(subject=title, #subj 
                           body=rendered_text, #body
                           from_email=settings.EMAIL_LOGIN, #from
                           to=settings.LOGTRACKER_ALERT_EMAILS,#to
                           connection=conn
                           )
        
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
        #send_mail(title, rendered_text, settings.EMAIL_LOGIN, settings.LOGTRACKER_ALERT_EMAILS, fail_silently=True)
post_save.connect(sendAlert, sender=LogTrack)