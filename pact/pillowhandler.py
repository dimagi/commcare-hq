from corehq.pillows.core import formats_string
from corehq.pillows.xform import XFormPillowHandler

class PactHandler(XFormPillowHandler):
    domain = "pact"

    def has_custom_mapping(self, doc_dict):
        xmlns = doc_dict['xmlns']
        if doc_dict['domain'] == 'pact':
            return True

        #        if xmlns == "http://dev.commcarehq.org/pact/dots_form":
        #            return True
        #        if xmlns == "http://dev.commcarehq.org/pact/progress_note":
        #            return True
        #        if xmlns == "http://dev.commcarehq.org/pact/bloodwork":
        #            return True

        return False

    def get_custom_mapping(self, doc_dict, mapping=None):
        xmlns = doc_dict['xmlns']
        print "get custom mapping: %s" % xmlns
        if xmlns == "http://dev.commcarehq.org/pact/dots_form":
            mapping['properties']['form']['properties']['encounter_date'] = {
                "type": "date",
                "format": formats_string
            }
        if xmlns == "http://dev.commcarehq.org/pact/progress_note":
            mapping['properties']['form']['properties']['note'] = {
                'properties': {
                    'encounter_date': {
                        "type": "date",
                        "format": formats_string
                    },
                    "bwresults": {
                        "dynamic": "true",
                        "properties": {
                            "bw": {
                                "dynamic": "true",
                                "properties": {
                                    "test_date": {
                                        "type": "date",
                                        "format": formats_string
                                    },
                                }
                            }
                        }
                    },
                }
            }
            #                [{"bw": {"tests": "vl cd", "vl": "11400", "test_date": "2011-07-29", "cd": {"cdper": "", "cdcnt": "118"}}}, {"referral": {"ref_type": "medical", "ref_date": "2011-07-28"}}]

        if xmlns == "http://dev.commcarehq.org/pact/bloodwork":
        #                [{"bw": {"tests": "vl cd", "vl": "11400", "test_date": "2011-07-29", "cd": {"cdper": "", "cdcnt": "118"}}}, {"referral": {"ref_type": "medical", "ref_date": "2011-07-28"}}]
            #convert all bw dicts to array, even singletons (dict)
            #turn "" to null
            #check test_date and ref_date for blanks, convert to None
            mapping['properties']['form']['properties']['results'] = {
                "dynamic": "true",
                "properties": {
                    "bw": {
                        "dynamic": "true",
                        "properties": {
                            "test_date": {
                                "type": "date",
                                "format": formats_string
                            },
                        }
                    }
                }
            }
            pass
        print "returning mapping"
        return mapping

    def do_transform(self, doc_dict):
        """
        Todo: implement criteria for transformation
        """
        return False

    def handle_transform(self, doc_dict):
        #sanity check for date_modified
        if doc_dict.get('form', {}).has_key('case'):
            #old and new check
            date_modified_keys = ['date_modified', '@date_modified']

            for k in date_modified_keys:
                if doc_dict['form']['case'].has_key(k):
                    if doc_dict['form']['case'][k] == "":
                    #                        print "fixing null date modified: %s" % doc_dict['_id']
                        doc_dict['form']['case'][k] = None

            if doc_dict['form']['meta'].get('timeEnd', None) == "":
                doc_dict['form']['meta']['timeEnd'] = None
                #                print "fixing null timeEnd"

            if doc_dict['form']['meta'].get('timeStart', None) == "":
                doc_dict['form']['meta']['timeStart'] = None
                #                print "fixing null timeStart"

            if doc_dict.get('received_on', None) == "":
                doc_dict['received_on'] = None
                #                print "fixing null received_on"

            if not isinstance(doc_dict.get('form', {}).get('case', {}).get('update', {}), dict):
                print "fixing blank string case.update"
                doc_dict['form']['case']['update'] = None

            if doc_dict['xmlns'] == "http://dev.commcarehq.org/pact/dots_form":
                if doc_dict['form'].get('question', None) == "":
                    doc_dict['form']['question'] = {}
                    #                    print "fixing blank dots.form.question"

            if doc_dict['xmlns'] == "http://dev.commcarehq.org/pact/progress_note":
                bw_main = doc_dict['form']['note'].get('bwresults', None)
                if isinstance(bw_main, str):
                    doc_dict['form']['note']['bwresults'] = None
                elif isinstance(bw_main, dict):
                    bw_results = doc_dict['form']['note']['bwresults'].get('bw', None)
                    if isinstance(bw_results, dict):
                        #single instance, make it a list
                        print "fixing single pn bloodwork: %s" % doc_dict['_id']
                        doc_dict['form']['note']['bwresults']['bw'] = [bw_results]
                    elif isinstance(bw_results, str):
                        print "fixing null pn bloodwork: %s #%s#" % (doc_dict['_id'], bw_results)
                        doc_dict['form']['note']['bwresults']['bw'] = None

                        #dots blank case update (it's dynamic)
                        #bw results blank, it's dynamic
            if doc_dict['xmlns'] == "http://dev.commcarehq.org/pact/bloodwork":
                bw_main = doc_dict['form'].get('results', None)
                if isinstance(bw_main, str):
                    doc_dict['form']['results'] = None
                elif isinstance(bw_main, dict):
                    bw_results = doc_dict['form']['results'].get('bw', None)
                    if isinstance(bw_results, dict):
                        print "fixing single bw bloodwork: %s" % doc_dict['_id']
                        #single instance, make it a list
                        doc_dict['form']['results']['bw'] = [bw_results]
                    elif isinstance(bw_results, str):
                        print "fixing null bw bloodwork: %s #%s#" % (doc_dict['_id'], bw_results)
                        doc_dict['form']['results']['bw'] = None
        return doc_dict
