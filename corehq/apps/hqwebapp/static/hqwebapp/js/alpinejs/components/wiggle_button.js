/**
 * Use this model to create user delight!
 * Encourage interaction with a button by making it wiggle
 * when the user hovers over it, or clicks it.
 *
 * Use this by importing the model before Alpine.start() like this:
 *
 *   import wiggleButton from 'hqwebapp/js/alpinejs/components/wiggle_button';
 *   Alpine.data('wiggleButtonModel', wiggleButton);
 *
 * Here is an example for a click-to-wiggle button on your page
 * using this model:
 *
 *   Somewhere on the page you might have this text:
 *
 *     No records were found that match the current filters. Please
 *     <a
 *       href="#"
 *       class="fw-bold"
 *       @click.prevent="$dispatch('wiggle-filters-button');"
 *     >adjust your filters</a> and try again.
 *
 *   Your filters button might look like this:
 *
 *     <button
 *       type="button"
 *       class="btn btn-outline-primary"
 *       x-model="wiggleButtonModel"
 *       @wiggle-filters-button.window="wiggleThatButton()"
 *       :class="getWiggleClasses()"
 *     >Filter Records</button>
 *
 *   Is your button not `btn-outline-primary`? No problem! Just pass in
 *   the classes as arguments in your model:
 *
 *      x-model="wiggleButtonModel('btn-secondary', 'btn-outline-secondary')"
 *
 */
export default (
    onStateClasses = 'btn-primary',
    offStateClasses = 'btn-outline-primary',
) => ({
    isWiggling: false,
    onStateClasses: onStateClasses + ' btn-wiggle',
    offStateClasses: offStateClasses,
    wiggleThatButton() {
        this.isWiggling = true;
        setTimeout(() => {
            this.isWiggling = false;
        }, 1000);
    },
    getWiggleClasses() {
        let cssClasses = {};
        cssClasses[this.onStateClasses] = this.isWiggling;
        cssClasses[this.offStateClasses] = !this.isWiggling;
        return cssClasses;
    },
});
