import pdb
from django.test import TestCase
from pact.enums import PACT_REGIMEN_CHOICES, DOT_NONART, DOT_ART, CASE_NONART_REGIMEN_PROP, CASE_ART_REGIMEN_PROP
from pact.regimen import regimen_dict_from_choice, regimen_string_from_doc

art_nonart = [DOT_ART, DOT_NONART]

class RegimenPropertiesTests(TestCase):
    def testStringToDictRegimensNum(self):
        #assure that all frequencies line up ok
        for freq in range(1,5):
            regimens = PACT_REGIMEN_CHOICES[freq][1]
            for drug_type in art_nonart:
                for regimen_tuple in regimens:
                    ret = regimen_dict_from_choice(drug_type, regimen_tuple[0])

                    if drug_type == DOT_ART:
                        key_type_string = CASE_ART_REGIMEN_PROP
                    elif drug_type == DOT_NONART:
                        key_type_string = CASE_NONART_REGIMEN_PROP
                    self.assertEquals(ret[key_type_string], str(freq))

    def testStringToLabelValues(self):
        """
        From the string representation of the selected regimen, create the case properties representing this


        Note, hacky form right now assumes all these properties are resolved as strings - if changes come to the xforms that submit these values as ints, then
        equality will need to be changed.
        """

        qid = 'morning,noon,evening,bedtime' #0,1,2,3
        tid_shift = 'noon,evening,bedtime' #1,2,3
        bd_extremes = 'morning,bedtime' #0,3
        qd_eve = 'evening' #2

        qid_ret = regimen_dict_from_choice(DOT_ART, qid)
        self.assertEquals(qid_ret, {'dot_a_one': '0', 'dot_a_four': '3', 'dot_a_two': '1', 'artregimen': '4', 'dot_a_three': '2'})

        tid_ret = regimen_dict_from_choice(DOT_ART, tid_shift)
        self.assertEquals(tid_ret, {'dot_a_one': '1', 'dot_a_four': '', 'dot_a_two': '2', 'artregimen': '3', 'dot_a_three': '3'})

        bd_ret = regimen_dict_from_choice(DOT_ART, bd_extremes)
        self.assertEquals(bd_ret, {'dot_a_one': '0', 'dot_a_four': '', 'dot_a_two': '3', 'artregimen': '2', 'dot_a_three': ''})

        qd_ret = regimen_dict_from_choice(DOT_ART, qd_eve)
        self.assertEquals(qd_ret, {'dot_a_one': '2', 'dot_a_four': '', 'dot_a_two': '', 'artregimen': '1', 'dot_a_three': ''})


    def testStringFromRegimenProps(self):
        """
        From the regimen props of the case - get the string representation of the label choices
        """

        qid = {'dot_n_one': '0', 'dot_n_four': '3', 'dot_n_two': '1', 'nonartregimen': '4', 'dot_n_three': '2'} #morning,noon,evening,bedtime
        tid = {'dot_a_one': '0', 'dot_a_four': '', 'dot_a_two': '1', 'artregimen': '3', 'dot_a_three': '3'} #morning, noon, bedtime
        bd = {'dot_n_one': '1', 'dot_n_four': '', 'dot_n_two': '2', 'nonartregimen': '2', 'dot_n_three': ''} #noon, evening
        qd_noon = {'dot_a_one': '1', 'dot_a_four': '', 'dot_a_two': '', 'artregimen': '1', 'dot_a_three': ''} #noon
        qd_evening = {'dot_n_one': '2', 'dot_n_four': '', 'dot_n_two': '', 'nonartregimen': '1', 'dot_n_three': ''} #evening

        qid_str = regimen_string_from_doc(DOT_NONART, qid)
        self.assertEquals(qid_str, 'morning,noon,evening,bedtime')

        tid_str = regimen_string_from_doc(DOT_ART, tid)
        self.assertEquals(tid_str, 'morning,noon,bedtime')

        bd_str = regimen_string_from_doc(DOT_NONART, bd)
        self.assertEquals(bd_str, 'noon,evening')

        qd_noon_str = regimen_string_from_doc(DOT_ART, qd_noon)
        self.assertEquals(qd_noon_str, 'noon')

        qd_evening_str = regimen_string_from_doc(DOT_NONART, qd_evening)
        self.assertEquals(qd_evening_str, 'evening')






