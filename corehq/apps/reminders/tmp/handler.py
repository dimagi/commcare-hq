class ReminderHandlerDefault():
    def outgoing_sms(self, number, text):
        print(number + ":" + text)
    
    def incoming_sms(self, number, text):
        pass
    
    def incoming_call(self, number, text):
        pass

