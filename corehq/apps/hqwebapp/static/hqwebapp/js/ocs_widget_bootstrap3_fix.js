/**
 * Open Chat Studio Widget Bootstrap 3 Compatibility Fix
 *
 * This script overrides the widget's internal styles to ensure consistent sizing
 * between Bootstrap 3 and Bootstrap 5, since CSS custom properties don't work
 * in shadow DOM.
 */
'use strict';

(function () {

    // Create a style element that will be injected into any shadow root
    const styleOverride = document.createElement('style');
    styleOverride.id = 'ocs-bootstrap3-fix';
    styleOverride.textContent = `
      /* Override Tailwind's rem-based sizing for Bootstrap 3 compatibility */
      .chat-btn-text span {
        font-size: 14px !important; /* Force consistent text size */
      }

      .chat-btn-text {
        font-size: 12px !important; /* Force consistent button size */
        padding: 12px 16px !important; /* Force consistent padding */
      }

      .chat-btn-text img {
        width: 24px !important; /* Force consistent icon size */
        height: 24px !important;
      }

      /* Override any other rem-based sizing */
      .text-sm {
        font-size: 14px !important;
      }

      .text-xs {
        font-size: 12px !important;
      }

      .px-3 {
        padding-left: 12px !important;
        padding-right: 12px !important;
      }

      .py-3 {
        padding-top: 12px !important;
        padding-bottom: 12px !important;
      }

      .w-6 {
        width: 24px !important;
      }

      .h-6 {
        height: 24px !important;
      }

      .gap-2 {
        gap: 8px !important;
      }

      /* Ensure consistent button sizing */
      .chat-btn-icon {
        width: 56px !important;
        height: 56px !important;
      }

      .chat-btn-icon img {
        width: 24px !important;
        height: 24px !important;
      }

      /* Fix chat window font sizes */
      #ocs-chat-window .text-sm {
        font-size: 14px !important;
      }

      #ocs-chat-window .text-xs {
        font-size: 12px !important;
      }

      #ocs-chat-window p {
        font-size: 14px !important;
        line-height: 1.5 !important;
      }

      #ocs-chat-window .chat-markdown {
        font-size: 14px !important;
      }

      #ocs-chat-window .chat-markdown p {
        font-size: 14px !important;
        margin-bottom: 0.5rem !important;
      }

      #ocs-chat-window .chat-markdown ol,
      #ocs-chat-window .chat-markdown ul {
        font-size: 14px !important;
      }

      #ocs-chat-window .chat-markdown li {
        font-size: 14px !important;
      }

      #ocs-chat-window .chat-markdown strong {
        font-size: 14px !important;
      }

      /* Fix textarea and input font sizes */
      #ocs-chat-window textarea {
        font-size: 14px !important;
      }

      #ocs-chat-window input {
        font-size: 14px !important;
      }

      #ocs-chat-window button {
        font-size: 14px !important;
      }

      /* Fix header and navigation elements */
      #ocs-chat-window .size-6 {
        width: 24px !important;
        height: 24px !important;
      }

      #ocs-chat-window .p-1\\.5 {
        padding: 6px !important;
      }

      #ocs-chat-window .px-2 {
        padding-left: 8px !important;
        padding-right: 8px !important;
      }

      #ocs-chat-window .py-2 {
        padding-top: 8px !important;
        padding-bottom: 8px !important;
      }

      #ocs-chat-window .px-4 {
        padding-left: 16px !important;
        padding-right: 16px !important;
      }

      #ocs-chat-window .py-2 {
        padding-top: 8px !important;
        padding-bottom: 8px !important;
      }

      #ocs-chat-window .gap-1 {
        gap: 4px !important;
      }

      #ocs-chat-window .gap-0\\.5 {
        gap: 2px !important;
      }

      #ocs-chat-window .gap-2 {
        gap: 8px !important;
      }

      /* Fix spacing in chat messages */
      #ocs-chat-window .space-y-2 > * + * {
        margin-top: 8px !important;
      }

      #ocs-chat-window .mt-1 {
        margin-top: 4px !important;
      }

      #ocs-chat-window .ml-2 {
        margin-left: 8px !important;
      }
    `;

    // Function to inject styles into shadow root
    function injectStylesIntoShadowRoot(shadowRoot) {
        // Check if we've already added our override styles
        if (shadowRoot.querySelector('#ocs-bootstrap3-fix')) {
            return;
        }

        // Clone the style element and add it to the shadow root
        const clonedStyle = styleOverride.cloneNode(true);
        shadowRoot.appendChild(clonedStyle);

        // Add class to widget to make it visible
        const widget = shadowRoot.host;
        if (widget) {
            widget.classList.add('bootstrap3-fixed');
        }
    }

    // Function to check and fix widget
    function checkAndFixWidget() {
        const widget = document.querySelector('open-chat-studio-widget');
        if (widget && widget.shadowRoot) {
            injectStylesIntoShadowRoot(widget.shadowRoot);
        }
    }

    // More aggressive polling to catch the widget as early as possible
    function aggressivePolling() {
        let attempts = 0;
        const maxAttempts = 100; // 10 seconds max

        const poll = () => {
            attempts++;
            checkAndFixWidget();

            if (attempts < maxAttempts) {
                setTimeout(poll, 100);
            }
        };

        poll();
    }

    aggressivePolling();
})();
