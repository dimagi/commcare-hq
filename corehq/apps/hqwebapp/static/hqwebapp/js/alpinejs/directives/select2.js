import $ from 'jquery';
import 'select2/dist/js/select2.full.min';
import Alpine from 'alpinejs';

Alpine.directive('select2', (el, { expression }) => {
    /*
        To use, add x-select2 to your select element.
        <select x-select2>

        This is especially useful in crispy forms for a choice field:
        self.helper.layout = crispy.Layout(
            ...
            crispy.Field(
                'choice_field',
                x_select2=json.dumps({
                    "placeholder: "foo",
                    ...
                }),
            ),
            ...
        )
     */
    const options = (expression) ? JSON.parse(expression) : {};
    $(el).select2(options);
});
