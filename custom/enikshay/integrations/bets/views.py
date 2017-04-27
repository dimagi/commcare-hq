from corehq.apps.repeaters.views import AddCaseRepeaterView


class BETSVoucherRepeaterView(AddCaseRepeaterView):
    urlname = 'bets_voucher_repeater'
    page_title = "BETS Vouchers"
    page_name = "BETS Vouchers"

