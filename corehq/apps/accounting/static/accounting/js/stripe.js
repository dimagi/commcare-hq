import { loadStripe } from '@stripe/stripe-js';

self.stripePromise = undefined;
self.cardElement = undefined;

function getCardElementPromise(key) {
    let promise = new Promise((resolve) => {
        if (!key) {
            console.warn("Cannot load Stripe, key not provided");
            return;
        }
        self.stripePromise = loadStripe(key);
        self.stripePromise.then(function (stripe) {
            self.cardElement = stripe.elements().create('card', {
                hidePostalCode: true,
            });
            resolve(self.cardElement);
        });
    });

    return promise;
}

function createStripeToken(handleResponse) {
    self.stripePromise.then(function (stripe) {
        stripe.createToken(self.cardElement).then(handleResponse);
    });
}

export { createStripeToken, getCardElementPromise };
