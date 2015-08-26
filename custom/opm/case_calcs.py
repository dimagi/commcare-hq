"""
Fluff calculators that pertain to specific cases/beneficiaries (mothers).
These are used in the Beneficiary Payment Report
"""
import datetime
import fluff

class VhndAvailabilityCalc(fluff.Calculator):

    def dates_from_forms(self, case, condition):
        """
        Condition should accept a form and return a boolean
        """
        available = False
        for form in case.get_forms():
            vhnd_date = form.form.get("date_vhnd_held")
            if isinstance(vhnd_date, (datetime.datetime, datetime.date)):
                if condition(form):
                    available = True
                    yield vhnd_date
        if not available:
            yield [datetime.date.min, 0]

    def dates_available(self, case, prop):
        return self.dates_from_forms(case, lambda form: form.form.get(prop) == '1')

    @fluff.date_emitter
    def available(self, case):
        return self.dates_from_forms(case, lambda form: True)

    @fluff.date_emitter
    def asha_present(self, case):
        return self.dates_available(case, "attend_ASHA")

    @fluff.date_emitter
    def anm_present(self, case):
        return self.dates_available(case, "attend_ANM")

    @fluff.date_emitter
    def cmg_present(self, case):
        return self.dates_available(case, "attend_cmg")

    @fluff.date_emitter
    def ifa_available(self, case):
        return self.dates_available(case, "stock_ifatab")

    @fluff.date_emitter
    def adult_scale_available(self, case):
        return self.dates_available(case, "stock_bigweighmach")

    @fluff.date_emitter
    def child_scale_available(self, case):
        return self.dates_available(case, "stock_childweighmach")

    @fluff.date_emitter
    def adult_scale_functional(self, case):
        return self.dates_available(case, "func_bigweighmach")

    @fluff.date_emitter
    def child_scale_functional(self, case):
        return self.dates_available(case, "func_childweighmach")

    @fluff.date_emitter
    def ors_available(self, case):
        return self.dates_available(case, "stock_ors")

    @fluff.date_emitter
    def zn_available(self, case):
        return self.dates_available(case, "stock_zntab")

    @fluff.date_emitter
    def measles_vacc_available(self, case):
        return self.dates_available(case, "stock_measlesvacc")
