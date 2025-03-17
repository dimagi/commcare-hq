import { Modal } from "bootstrap5";

const DEFAULT_MODAL_ID = 'htmxRequestErrorModal';

/**
 * Displays an error modal for HTMX request errors, and dispatches an event to update modal content.
 * The default modal template can be found at
 * `hqwebapp/htmx/error_modal.html`
 * You can extend this template and include it in the `modals` block of a template that extends one
 * of HQ's base templates.
 *
 * @param {number} errorCode - The HTTP error code representing the type of error.
 * @param {string} errorText - A descriptive error message to display in the modal.
 * @param {string} [errorModalId=DEFAULT_MODAL_ID] - The ID of the modal element in the DOM (default is `DEFAULT_MODAL_ID`).
 */
const showHtmxErrorModal = (errorCode, errorText, errorModalId = DEFAULT_MODAL_ID) => {
    const modalElem = document.getElementById(errorModalId);
    if (!modalElem) {return;} // Exit if modal element is not found

    const errorModal = new Modal(modalElem);
    window.dispatchEvent(new CustomEvent('updateHtmxRequestErrorModal', {
        detail: {
            errorCode: errorCode,
            errorText: errorText,
        },
    }));
    errorModal.show();
};

export { showHtmxErrorModal };
