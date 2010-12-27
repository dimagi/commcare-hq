
def send_sms_messages(phone_numbers = [], text=''):
    for phone_number in phone_numbers:
        send_sms(phone_number, text)
        
def send_sms(phone_number, text):
    # temporary placeholder
    print "sending %s to %s" % (text, phone_number)
