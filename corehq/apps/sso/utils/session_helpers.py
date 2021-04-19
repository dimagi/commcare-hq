def store_saml_data_in_session(request):
    """
    This stores SAML-related authentication data in the request's session
    :param request: HttpRequest
    """
    request.session['samlUserdata'] = request.saml2_auth.get_attributes()
    request.session['samlNameId'] = request.saml2_auth.get_nameid()
    request.session['samlNameIdFormat'] = request.saml2_auth.get_nameid_format()
    request.session['samlNameIdNameQualifier'] = request.saml2_auth.get_nameid_nq()
    request.session['samlNameIdSPNameQualifier'] = request.saml2_auth.get_nameid_spnq()
    request.session['samlSessionIndex'] = request.saml2_auth.get_session_index()
