from django.utils.translation import ugettext_lazy as _

INVALID_MESSAGE = _('Sorry, I could not understand your message.'
                    ' Please contact your DHIO for help, or visit http://www.ewsghana.com')

INVALID_PRODUCT_CODE = _('%s is not a recognized commodity code. Please contact your DHIO or RHIO for help.')

ASSISTANCE_MESSAGE = _('Please contact your DHIO or RHIO for assistance.')

MS_STOCKOUT = _('The %(ms_type)s has reported a stockout of %(products_names)s. '
                'You will be informed when the stockout situation is reversed.')

MS_RESOLVED_STOCKOUTS = _('The following commodities %(products_names)s are now available at the %(ms_type)s. '
                          'Please place your order now.')
