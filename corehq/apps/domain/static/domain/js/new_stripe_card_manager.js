import htmx from "htmx.org";
import { createStripeToken, getCardElementPromise } from "accounting/js/stripe";
import initialPageData from "hqwebapp/js/initial_page_data";

export default (stripeApiKey, paymentMethodContainerId, cardContainerSelector, cardModalId, csrfToken) => ({
    stripeApiKey: stripeApiKey,
    paymentMethodContainerId: paymentMethodContainerId,
    cardContainerSelector: cardContainerSelector,
    cardModalId: cardModalId,
    csrfToken: csrfToken,
    isAutopay: false,
    isProcessing: false,
    cardElementMounted: false,
    cardElementPromise: null,
    successMsg: '',
    errorMsg: '',
    init() {
        this.cardElementPromise = getCardElementPromise(this.stripeApiKey);
        this.cardElementPromise.then((cardElement) => {
            cardElement.mount(this.cardContainerSelector);
            this.cardElementMounted = true;
        });
    },
    reset() {
        this.isAutopay = false;
        if (this.cardElementMounted) {
            this.cardElementPromise.then((cardElement) => {
                cardElement.clear();
            });
        }
    },
    saveCard() {
        this.isProcessing = true;
        createStripeToken((result) => {
            if (result.error) {
                this.isProcessing = false;
                this.errorMsg = result.error.message;
            } else {
                this.errorMsg = '';
                const cardToken = result.token.id;
                const formData = new FormData();
                formData.append('token', cardToken);
                formData.append('autopay', this.isAutopay);
                formData.append('csrfmiddlewaretoken', this.csrfToken);
                const createCardPromise = fetch(initialPageData.reverse("cards_view", cardToken), {
                    method: 'POST',
                    body: formData,
                });
                createCardPromise.then((response) => {
                    if (!response.ok) {
                        response.json().then((data) => {
                            this.errorMsg = data.error;
                        });
                    } else {
                        this.successMsg = gettext('Card added successfully! Refreshing cards list...');
                        this.reset();
                        htmx.trigger(document.getElementById(this.paymentMethodContainerId), "refreshCards");
                        setTimeout(() => {
                            this.successMsg = '';
                        }, 3000);
                    }
                }).catch((error) => {
                    this.errorMsg = error;
                }).finally(() => {
                    this.isProcessing = false;
                });
            }
        });
    },
});
