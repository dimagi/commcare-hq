import gtx from 'analytix/js/gtx';
import logging from 'analytix/js/logging';
import Alpine from 'alpinejs';

const _logger = logging.getLoggerForApi('GTM - Alpine');

Alpine.store('gtm', {
    /**
     * Sends an event to Google Tag Manager from alpine js event handlers.
     *
     * Example usage:
     * ```html
     * <button @click="$store.gtm.sendEvent('buttonClicked', { buttonId: 'myButton' })">
     * ```
     * @param {string} name - The name of the event to send.
     * @param {Object} [data={}] - Additional data to include with the event.
     */
    sendEvent(name, data = {}) {
        _logger.debug.log(`event triggered: ${name}`);
        _logger.debug.log(data);
        gtx.sendEvent(name, data);
    },
});
