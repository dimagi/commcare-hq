from __future__ import absolute_import
import logging.handlers
import smtplib

# this is a handler for the python logging framework that is capable
# of sending email alerts from a gmail account (the built-in email
# handler doesn't support TLS)

class TLSSMTPHandler(logging.handlers.SMTPHandler):
    def emit(self, record):
        headers = []

        headers.append(('From', self.fromaddr))
        headers.append(('To', ', '.join(self.toaddrs)))
        headers.append(('Subject', self.getSubject(record)))
        headers.append(('Date', self.date_time()))
        headers.append(('Mime-Version', '1.0'))
        headers.append(('Content-Type', '%s; charset="%s";' % ('text/plain', 'ISO-8859-1')))
        headers.append(('Content-Transfer-Encoding', '7bit'))

        header = '\r\n'.join('%s: %s' % h for h in headers)
        content = self.format(record)

        server = smtplib.SMTP(self.mailhost, self.mailport)
        server.set_debuglevel(0)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(self.username, self.password)
        server.sendmail(self.fromaddr, self.toaddrs, '%s\r\n\r\n%s' % (header, content))
        server.quit()

def example_setup():
    root = logging.getLogger()
    root.setLevel(logging.ERROR)
    handler = TLSSMTPHandler(
        ('smtp.gmail.com', 587),
        'Uptime Monitor <uptime@dimagi.com>',
        RECIPIENTS,
        'major error!',
        ('emailacct@dimagi.com', SMTP_PASS)
    )
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    root.addHandler(handler)
