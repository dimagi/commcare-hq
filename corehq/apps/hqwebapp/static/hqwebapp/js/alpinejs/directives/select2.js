import $ from 'jquery';
import 'select2/dist/js/select2.full.min';
import Alpine from 'alpinejs';


Alpine.directive('select2', (el, { expression }, { cleanup }) => {
    /**
     * To use, add x-select2 to your select element.
     *
     *      <select x-select2></select>
     *          or
     *      <select x=select2="{{ options|JSON }}"></select>
     *
     * This is especially useful in crispy forms for a choice field:
     *
     * self.helper.layout = crispy.Layout(
     *     ...
     *     crispy.Field(
     *         'choice_field',
     *         x_select2=json.dumps({
     *             "placeholder: "foo",
     *             ...
     *         }),
     *     ),
     *     ...
     * )
     */
    const options = (expression) ? JSON.parse(expression) : {};
    $(el).select2(options);

    cleanup(() => {
        if ($(el).data('select2')) {
            $(el).select2('destroy');
            $(el).off('select2:select');
        }
    });
});

document.body.addEventListener('htmx:afterSettle', (event) => {
    /**
     * This fixes a bug for forms using x-select2 after submitting, validating, and swapping back into
     * the DOMusing HTMX.
     *
     * Without this fix, you will get the **visible** <select> stacked on top of the select2, and no
     * validation classes are passed to it.
     */
    event.target.querySelectorAll('[x-select2]').forEach((el) => {
        const activeSelect2 = $(el).data('select2');
        if (activeSelect2) {
            $(el).addClass('select2-hidden-accessible');
            const validationClasses = ['is-valid', 'is-invalid'];
            validationClasses.forEach((validationClass) => {
                if ($(el).hasClass(validationClass)) {
                    activeSelect2.$container.addClass(validationClass);
                }
            });
        }
    });
});
