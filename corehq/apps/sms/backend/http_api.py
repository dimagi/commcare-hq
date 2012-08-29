from urllib import urlencode
from urllib2 import urlopen

API_ID = "HTTP"

def send(msg, *args, **kwargs):
    """
    Expected kwargs:
        url                 the url to send to
        message_param       the parameter which the gateway expects to represent the sms message
        number_param        the parameter which the gateway expects to represent the phone number to send to
        include_plus        True to include the plus sign in front of the number, false not to (optional, defaults to false)
        method              "GET" or "POST" (optional, defaults to "GET")
        additional_params   a dictionary of additional parameters that will be sent in the request (optional, defaults to {})
    """
    url = kwargs.get("url")
    include_plus = kwargs.get("include_plus", False)
    method = kwargs.get("method", "GET")
    params = kwargs.get("additional_params", {})
    #
    phone_number = msg.phone_number
    if include_plus:
        if phone_number[0] != "+":
            phone_number = "+" + phone_number
    else:
        if phone_number[0] == "+":
            phone_number = phone_number[1:]
    #
    params[kwargs["message_param"]] = msg.text
    params[kwargs["number_param"]] = phone_number
    #
    url_params = urlencode(params)
    if method == "GET":
        response = urlopen(url + "?" + url_params).read()
    else:
        response = urlopen(url, url_params).read()

