

def fail(request, domain):
    # if you want to play with it, wire this to a url
    raise Exception("HQ Couchlog simulated failure in domain %s!" % domain)
