import fluff


class PncImmunizationCalculator(fluff.Calculator):
    def __init__(self, value):
        super(PncImmunizationCalculator, self).__init__()
        self.immunization_given_value = value

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child":
            for form in case.get_forms():
                if self.immunization_given_value in form.form.get("immunization_given", ""):
                    yield[form.received_on, 1]


class PncFullImmunizationCalculator(fluff.Calculator):

    @fluff.date_emitter
    def total(self, case):
        if case.type == "child" and case.get_case_property("immunization_given") is not None:
            full_immunization_values = ['opv_0', 'hep_b_0', 'bcg', 'opv_1', 'hep_b_1', 'penta_1', 'dpt_1',
                                        'pcv_1', 'opv_2', 'hep_b_2', 'penta_2', 'dpt_2', 'pcv_2', 'opv_3', 'penta_3',
                                        'dpt_3', 'pcv_3', 'measles_1', 'yellow_fever', 'measles_2', 'conjugate_csm']
            if all(value in case.get_case_property("immunization_given") for value in full_immunization_values):
                yield[case.modified_on, 1]
