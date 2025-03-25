import { loadStripe } from '@stripe/stripe-js';

self.stripePromise = undefined;
self.cardElement = undefined;

function getCardElementPromise(key) {
    if (!key) {
        throw new Error("Cannot load Stripe, key not provided");
    }

    let promise = new Promise((resolve) => {
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
};

export { createStripeToken, getCardElementPromise };
