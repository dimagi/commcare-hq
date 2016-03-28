import re
from collections import OrderedDict

from corehq.apps.commtrack.sms import SMSError


class EWSFormatter(object):

    REC_SEPARATOR = '-'

    def _clean_string(self, string):
        if not string:
            return string
        mylist = list(string)
        newstring = string[0]
        i = 1
        while i < len(mylist) - 1:
            if mylist[i] == ' ' and mylist[i - 1].isdigit() and mylist[i + 1].isdigit():
                newstring += self.REC_SEPARATOR
            else:
                newstring = newstring + mylist[i]
            i += 1
        newstring = newstring + string[-1]
        string = newstring

        string = string.replace(' ', '')
        separators = [',', '/', ';', '*', '+', '-']
        for mark in separators:
            string = string.replace(mark, self.REC_SEPARATOR)
        junk = ['\'', '\"', '`', '(', ')']
        for mark in junk:
            string = string.replace(mark, '')
        return string.lower()

    def _getTokens(self, string):
        mylist = list(string)
        token = ''
        i = 0
        while i < len(mylist):
            token = token + mylist[i]
            if i + 1 == len(mylist):
                # you've reached the end
                yield token
            elif (mylist[i].isdigit() and not mylist[i + 1].isdigit()
                  or mylist[i].isalpha() and not mylist[i + 1].isalpha()
                  or not mylist[i].isalnum() and mylist[i + 1].isalnum()):
                yield token
                token = ''
            i += 1

    def format(self, string):
        """
        Old parse method, used in Ghana for more 'interesting' parsing.
        Moved from: https://github.com/dimagi/rapidsms-logistics/blob/7a1433abbda4ec27dc8f4c5da14c0f5689abd202/logistics/models.py#L1430
        """
        if not string:
            return
        match = re.search("[0-9]", string)
        if not match:
            raise SMSError
        string = self._clean_string(string)
        an_iter = self._getTokens(string)
        commodity = None
        valid = False

        product_quantity = OrderedDict()
        while True:
            try:
                while commodity is None or not commodity.isalpha():
                    commodity = an_iter.next().lower()
                count = an_iter.next()
                while not count.isdigit():
                    count = an_iter.next()
                product_quantity[commodity] = {'soh': count, 'receipts': 0}
                valid = True
                token_a = an_iter.next()
                if not token_a.isalnum():
                    token_b = an_iter.next()
                    while not token_b.isalnum():
                        token_b = an_iter.next()
                    if token_b.isdigit():
                        # if digit, then the user is reporting receipts
                        product_quantity[commodity]['receipts'] = token_b
                        commodity = None
                        valid = True
                    else:
                        # if alpha, user is reporting soh, so loop
                        commodity = token_b
                        valid = True
                else:
                    commodity = token_a
                    valid = True
            except ValueError:
                commodity = None
                continue
            except StopIteration:
                break
        if not valid:
            return string

        result = ""
        for product, soh_receipt_dict in product_quantity.iteritems():
            soh = soh_receipt_dict.get('soh')
            if not soh:
                continue
            receipts = soh_receipt_dict.get('receipts', 0)
            result += "{} {}.{} ".format(product, soh, receipts)

        return result.strip()
