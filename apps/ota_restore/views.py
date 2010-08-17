# from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
# from django.http import HttpResponseRedirect
# from rapidsms.webui.utils import render_to_response

import os
import settings
import time, datetime

from django_digest.decorators import *

from xml.dom.minidom import parse, parseString
from receiver.models import Submission, Attachment
from xformmanager.models import Metadata
from phone.models import PhoneUserInfo

    
@httpdigest
def ota_restore(request):
    username = request.user.username
    # username = 'derik'
    
    cases_list = {}
        
    try:
        pu = PhoneUserInfo.objects.filter(username=username).filter(attachment__isnull=False)
        
        if len(pu) > 1:
            return HttpResponse("<error>Username '%s' attached to multiple phones</error>" % username, mimetype="text/xml")

        elif len(pu) < 1:
            return HttpResponse("<error>No phone linked to username '%s'</error>" % username, mimetype="text/xml")
        
        # OK, go on.
        reg = pu[0].attachment.get_contents()
        
        if reg == None:
            return HttpResponse("<error>Attachment %s empty or non-existant</error>" % pu[0].attachment, mimetype="text/xml")
        
        registration_xml = parseString(reg).getElementsByTagName("n0:registration")[0].toxml()
        
    except PhoneUserInfo.DoesNotExist:
        return HttpResponse("<error>No PhoneUser entry or entry without attachment for user '%s'</error>" % username, mimetype="text/xml")

    except Attachment.DoesNotExist:
        return HttpResponse("<error>Attachment not found: %s</error>" % pu[0].attachment_id, mimetype="text/xml")
        

    atts = Metadata.objects.filter(username=username)        

    for a in atts:
        path = a.attachment.filepath

        contents = open(path, "r").read()
        contents = contents.decode('utf-8','ignore')
        
        try:
            submit_date = a.attachment.submission.submit_time
        except:
            submit_date = None
            
        dom = parse(path)
        cases = dom.getElementsByTagName("case")
                
        for case in cases:
            date_modified = case.getElementsByTagName("date_modified")[0].firstChild.data
            
            if submit_date is not None:
                d_mod, ms = date_modified.split('.')
                xform_time = datetime.datetime.strptime(d_mod, '%Y-%m-%dT%H:%M:%S')

                if abs(xform_time - submit_date).days >= 14:
                    date_modified = datetime.datetime.strftime(submit_date, '%Y-%m-%dT%H:%M:%S')
            
            case_id = case.getElementsByTagName("case_id")[0].firstChild.data

            key = "%s:%s" % (date_modified, case_id)
            cases_list[key] = case
                
                
    # create the xml, sorted by timestamps
    
    xml = '<restoredata>\n%s' % registration_xml

    
    for case in sorted(cases_list.keys()):
        xml += cases_list[case].toprettyxml()

    xml += "</restoredata>"
    
    return HttpResponse(xml, mimetype="text/xml")
    
    
@httpdigest
def digest_test(request):
    # just for testing
    xml = '''<restoredata>
           <registration>
                <username>ctsims</username>
                <password>234</password>
                <uuid>3F2504E04F8911D39A0C0305E82C3301</uuid>
                <date>2009-08-12</date>
                <registering_phone_id>3F2504E04F8911D39A0C0305E82C3301</registering_phone_id>
                <user_data>
                    <data key="chw_id">13/43/DFA</data>
                </user_data>
           </registration>
           <case>
               	<case_id>04CBE782D7634F3CB825E4B2E224577A</case_id>
               	<date_modified>2010-04-07T15:52:18.356</date_modified>
               	<create>
               		<case_type_id>cc_pf_client</case_type_id>
               		<user_id>1</user_id>
               		<case_name>John Test</case_name>
               		<external_id>23</external_id>
               	</create>
               	<update>
               	  <pat_inits>JDT</pat_inits>
               	  <sex>m</sex>
               	  <dob>1998-02-01</dob>
               	  <village>Testica</village>
               	</update>
           </case>
           <case>
               	<case_id>89A47809C352441BBDA4EAABFE9F2E07</case_id>
               	<date_modified>2010-04-02T15:52:18.356</date_modified>
               	<create>
                    <case_type_id>cc_pf_client</case_type_id>
                    <user_id>1</user_id>
                    <case_name>Jane Test</case_name>
                    <external_id>54</external_id>
               	</create>
               	<update>
                    <pat_inits>JMT</pat_inits>
                    <sex>f</sex>
                    <dob>1993-02-01</dob>
                    <village>Testistan</village>
               	</update>
           </case>
           <case>
                <case_id>DFD3A4BCEAF54743AAC8E4190EBB77B6</case_id>
                <date_modified>2010-04-01T15:52:18.356</date_modified>
                <create>
                    <case_type_id>cc_pf_client</case_type_id>
                    <user_id>1</user_id>
                    <case_name>Patricia Demo</case_name>
                    <external_id>99</external_id>
                </create>
                <update>
                    <pat_inits>PRD</pat_inits>
                    <sex>f</sex>
                    <dob>1973-09-20</dob>
                    <village>Demonstria</village>
                </update>
           </case>
           <case>
               	<case_id>B0975B23FAB8496DA6EC83E42007824A</case_id>
               	<date_modified>2010-03-29T15:52:18.356</date_modified>
               	<create>
               		<case_type_id>cc_pf_client</case_type_id>
               		<user_id>1</user_id>
               		<case_name>Anthony Fictitious</case_name>
               		<external_id>3</external_id>
               	</create>
               	<update>
                    <pat_inits>AF</pat_inits>
                    <sex>m</sex>
                    <dob>1984-11-07</dob>
                    <village>None</village>
               	</update>
           </case>
           <case>
               	<case_id>80F6D28B0BFA414BBF8E05C4AEE145E9</case_id>
               	<date_modified>2010-03-23T15:52:18.356</date_modified>
               	<create>
                    <case_type_id>cc_pf_client</case_type_id>
                    <user_id>1</user_id>
                    <case_name>Robert</case_name>
                    <external_id>5</external_id>
               	</create>
               	<update>
                    <pat_inits>RPR</pat_inits>
                    <sex>m</sex>
                    <dob>1950-10-07</dob>
                    <village>Imaginatia</village>
               	</update>
           </case>
        </restoredata>
    '''
    return HttpResponse(xml, mimetype="text/xml") 





