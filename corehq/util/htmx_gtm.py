HTMX_GTM_EVENT_NAME = "hqHtmxGtmSendEvent"


def get_htmx_gtm_event(name, data=None):
    """
    Returns a dictionary that can be used to send an event to Google Tag Manager
    via HTMX. Add this to the HX-Trigger header in your HTMX response.

    Note: This function is best paired with `HqHtmxActionMixin`,
    calling/returning the following in an hq_hx_action method:
        self.include_gtm_event_with_response(response, name, data)

    :param name: The name of the event.
    :param data: Optional additional data to include with the event.
    :return: A dictionary formatted for HTMX GTM event handling.
    """
    return {
        HTMX_GTM_EVENT_NAME: {
            "name": name,
            "data": data or {},
        }
    }
