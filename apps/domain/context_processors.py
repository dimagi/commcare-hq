from domain.decorators import SESSION_KEY_SELECTED_DOMAIN

# Currently unused - formerly, we put domain info directly into the template context. Now it's in the user object.
# Keeping around for now, as a shell to be used if we do want to put domain info directly back into the template context.
def domain( request,
            selected_domain_key = SESSION_KEY_SELECTED_DOMAIN ):
    dom =  request.session.get(selected_domain_key, None)
    ret = {}
    if dom:
        ret['domain'] = dom
    return ret





