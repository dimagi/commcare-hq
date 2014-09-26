import fluff

class MotherRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        yield case.opened_on

class ChildRegistered(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        yield case.opened_on

class NumberChildren(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        total = 0
        if hasattr(case, 'number_of_children') and case.get_case_property('number_of_children') != '':
            total = int(case.get_case_property('number_of_children'))
        yield { 'date': case.opened_on, 'value': total }

class NumberBoys(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        total = 0
        if hasattr(case, 'number_of_boys') and case.get_case_property('number_of_boys') != '':
            total = int(case.get_case_property('number_of_boys'))
        yield { 'date': case.opened_on, 'value': total }

class NumberGirls(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        total = 0
        if hasattr(case, 'number_of_girls') and case.get_case_property('number_of_girls') != '':
            total = int(case.get_case_property('number_of_girls'))
        yield { 'date': case.opened_on, 'value': total }

class StillBirth(fluff.Calculator):
    @fluff.date_emitter
    def total(self, case):
        total = 0
        if hasattr(case, 'number_of_children_born_dead') and case.get_case_property('number_of_children_born_dead') != '':
            total = int(case.get_case_property('number_of_children_born_dead'))
        yield { 'date': case.opened_on, 'value': total }
