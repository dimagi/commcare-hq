import gtx from 'analytix/js/gtx';
import logging from 'analytix/js/logging';

const _logger = logging.getLoggerForApi('GTM - HTMX');

document.body.addEventListener('hqHtmxGtmSendEvent', (event) => {
    /**
     * Sends an event to Google Tag Manager from HTMX requests.
     *
     * This is best paired with `HqHtmxActionMixin` in Django views,
     * which call the following in an htmx action handler:
     * ```python
     * response = self.get(...)
     * return self.add_gtm_event_to_response(response, 'myEventName', {'key': 'value'})
     * ```
     */
    _logger.debug.log(`event triggered: ${event.detail.name}`);
    _logger.debug.log(event.detail.data);
    gtx.sendEvent(event.detail.name, event.detail.data);
});
