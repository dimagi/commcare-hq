from django.dispatch.dispatcher import Signal


sql_case_post_save = Signal(providing_args=["case"])
