from corehq.pillows.core import DATE_FORMATS_STRING
from corehq.pillows.xform import XFormPillowHandler

class PactHandler(XFormPillowHandler):
    domain = "pact"


    xmlns_mapping = {}

    def __init__(self, *args, **kwargs):
        self.xmlns_mapping = {
        "http://dev.commcarehq.org/pact/dots_form": self.dots_handler,
        "http://dev.commcarehq.org/pact/progress_note": self.pn_handler,
        "http://dev.commcarehq.org/pact/bloodwork": self.bw_handler
    }

    def has_custom_mapping(self, doc_dict):
        xmlns = doc_dict.get('xmlns', None)
        if doc_dict['domain'] == 'pact':
            return True

        #        if xmlns == "http://dev.commcarehq.org/pact/dots_form":
        #            return True
        #        if xmlns == "http://dev.commcarehq.org/pact/progress_note":
        #            return True
        #        if xmlns == "http://dev.commcarehq.org/pact/bloodwork":
        #            return True

        return False

    def dots_handler(self, doc_dict, mapping):
        mapping['dynamic'] = True
        mapping['properties']['form']['dynamic'] = True
        mapping['properties']['form']['properties']['encounter_date'] = {
            "type": "date",
            "format": DATE_FORMATS_STRING
        }

    def pn_handler(self, doc_dict, mapping):
        mapping['dynamic'] = True
        mapping['properties']['form']['dynamic'] = True
        mapping['properties']['form']['properties']['note'] = {
            'properties': {
                'encounter_date': {
                    "type": "date",
                    "format": DATE_FORMATS_STRING
                },
                "bwresults": {
                    "dynamic": "true",
                    "properties": {
                        "bw": {
                            "dynamic": "true",
                            "properties": {
                                "test_date": {
                                    "type": "date",
                                    "format": DATE_FORMATS_STRING
                                },
                            }
                        }
                    }
                },
            }
        }
    def bw_handler(self,doc_dict, mapping):
        #convert all bw dicts to array, even singletons (dict)
        #turn "" to null
        #check test_date and ref_date for blanks, convert to None
        mapping['dynamic'] = True
        mapping['properties']['form']['dynamic'] = True
        mapping['properties']['form']['properties']['results'] = {
            "dynamic": "true",
            "properties": {
                "bw": {
                    "dynamic": "true",
                    "properties": {
                        "test_date": {
                            "type": "date",
                            "format": DATE_FORMATS_STRING
                        },
                    }
                }
            }
        }

    def get_custom_mapping(self, doc_dict, mapping=None):
        xmlns = doc_dict.get('xmlns', None)
        print "get custom mapping: %s" % xmlns
        handler_func = self.xmlns_mapping.get(xmlns, None)
        if handler_func is not None:
            handler_func(doc_dict, mapping)
            print "handled"
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

            for datemod_key in date_modified_keys:
                if doc_dict['form']['case'].has_key(datemod_key):
                    if doc_dict['form']['case'][datemod_key] == "":
#                        print "try to fix null date modified: %s: %s" % (doc_dict['_id'], doc_dict['form']['case'][datemod_key])
                    #                        print "fixing null date modified: %s" % doc_dict['_id']
                        doc_dict['form']['case'][datemod_key] = None

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


            def bw_fixer(bw_key, subdict):
                bw_main = subdict.get(bw_key, None)
                if isinstance(bw_main, str):
                    subdict[bw_key] = None
                elif isinstance(bw_main, dict):
                    bw_results = subdict[bw_key].get('bw', None)
                    if isinstance(bw_results, dict):
                        #single instance, make it a list
                        print "fixing single %s bloodwork: %s" % (bw_key, doc_dict['_id'])
                        subdict[bw_key]['bw'] = [bw_results]
                    elif isinstance(bw_results, str):
                        print "fixing null %s bloodwork: %s #%s#" % (bw_key, doc_dict['_id'], bw_results)
                        subdict[bw_key]['bw'] = None

                #after fixing bw's to an array, check all test_dates
                if isinstance(subdict.get(bw_key, None), dict):
                    if subdict.get(bw_key, {}).has_key('bw'):
                        for ix, test in enumerate(subdict[bw_key]['bw']):
                            if test['test_date'] == "":
                                print "fixing blank test_date in bw %s" % doc_dict['_id']
                                subdict[bw_key]['bw'][ix]['test_date'] = None



            if doc_dict['xmlns'] == "http://dev.commcarehq.org/pact/progress_note":
                bw_fixer('bwresults', doc_dict['form']['note'])

            if doc_dict['xmlns'] == "http://dev.commcarehq.org/pact/bloodwork":
                bw_fixer('results', doc_dict['form'])

        return doc_dict
