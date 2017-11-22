# Guided Tours

With more complex user workflows, sometimes a step-by-step guide through a particular workflow is the fastest, most effective way to address user experience issues.

Ideally, the end goal should always be a simple workflow and immediately intuitive UI, but the real-world cannot always match this ideal.

## HQ's Library

We use the [Bootstrap Tour](http://bootstraptour.com/) library to run our guided tours. Usage is very [well documented](http://bootstraptour.com/api/), so if you need to do something out of the ordinary for a new tour, it might be good to consult the official docs.

## Setting up a Guided Tour

**1) Define `StaticGuidedTour`**

New tours are added in `corehq.apps.tour.tours`, where `my_tour` is the slug replaced for the slug of your tour.

```
MY_TOUR = StaticGuidedTour(
    'my_tour', 'tour/config/my_tour.html'
)
```

Ideally, you should *avoid* heavily subclassing `StaticGuidedTour`, as that will add ambiguity for the usage in the future. If you do subclass, please consider adding documentation for intended usage.
 
**2) Create the config for the tour in `tour/config/my_tour.html`**

```
<script>
    $(function () {
        var form_tour = new Tour({
            name: '{{ request.guided_tour.slug }}',
            orphan: true,  // required if the tour selectors are loaded asynchronously **after** the Tour is initialized
            steps: [
                {
                    element: '#<selector-id-to-highlight>',
                    title: gettext("Title Text"),
                    content: gettext("Content"),
                    placement: 'bottom',  // see Bootstrap Tour docs for usage
                    onShown: function () {
                        // this is a good callback to do fancy things like add analytics.
                        // other useful callbacks are `onHide`. 
                        hqImport('analytix/js/kissmetrics').track.event('comment');
                    }
                },
                // below is a good example if you wanted to add/remove classes to highlight the 
                // selectors that are part of the guided tour (or elements surrounding them)
                {
                    element: '#<selector-id-for-step-two>',
                    title: gettext("Step Two Title"),
                    content: gettext("Step Two Description"),
                    onShown: function () {
                        $('#<btn-selector>').addClass('btn-success').removeClass('btn-primary');
                    },
                    onHide: function () {
                        $('#<btn-selector>').removeClass('btn-success').addClass('btn-primary');
                    }
                },
                ... etc ...
            ],
            onEnd: TourUtils.getEndTourAsync('{{ request.guided_tour.endUrl }}'),  // Important to let the tour know that you've ended
            template: TourUtils.getCustomTemplate()
        });
        form_tour.setCurrentStep(0);  // Always start at step 0, otherwise start where the tour left off (noted in cookies)
        form_tour.init(true);
        form_tour.start(true);
    });
</script>
```

**3) Trigger the tour in your `View`**

```
from corehq.apps.tour import tours

...

class MyView(SomeTemplateView):

    # the dispatch method is likely a good choice for a class-based view to do
    # any server-side tour logic
    def dispatch(self, request, *args, **kwargs):
        if tours.MY_TOUR.is_enabled(request.user):
            request.guided_tour = tours.MY_TOUR.get_tour_data()
        return super(MyView, self).dispatch(request, *args, **kwargs)
```

Then in your `View`'s template, as long as somewhere along the line it extends `hqwebapp/base.html`:

```
{% block js-inline %}{{ block.super }}
{% if request.guided_tour %}{% include request.guided_tour.template %}{% endif %}
{% endblock %}
```


