from django.utils.translation import ugettext_lazy as _

INVALID_MESSAGE = _('Sorry, I could not understand your message.'
                    ' Please contact your DHIO for help, or visit http://www.ewsghana.com')

INVALID_PRODUCT_CODE = _('%s is not a recognized commodity code. Please contact your DHIO or RHIO for help.')

ASSISTANCE_MESSAGE = _('Please contact your DHIO or RHIO for assistance.')

MS_STOCKOUT = _('The %(ms_type)s has reported a stockout of %(products_names)s. '
                'You will be informed when the stockout situation is reversed.')

MS_RESOLVED_STOCKOUTS = _('The following commodities %(products_names)s are now available at the %(ms_type)s. '
                          'Please place your order now.')

STOP_MESSAGE = _('You have requested to stop reminders to this number. '
                 'Send "help" to this number for instructions on how to reactivate.')

START_MESSAGE = _('You have requested to receive reminders to this number. '
                  'Send "help" to this number for instructions on how to stop this.')

HELP_TEXT = _("Txt 'help stock' 4 the format of stock reports; 'help codes' 4 commodity codes; "
              "'start' or 'stop' 2 start and stop reminders.")

NO_SUPPLY_POINT_MESSAGE = "You are not associated with a facility. " \
                          "Please contact your DHIO or RHIO for help."
