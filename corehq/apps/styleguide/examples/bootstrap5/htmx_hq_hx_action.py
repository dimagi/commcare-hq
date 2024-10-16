from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq.apps.domain.decorators import login_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.prototype.models.cache_store import CacheStore
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
class TodoListDemoView(HqHtmxActionMixin, BasePageView):
    """
    This view demonstrates how we use HqHtmxActionMixin with a view to provide
    HTMX responses when HTMX interacts with this view using the `hq-hx-action` attribute.
    """
    urlname = "sg_htmx_todo_list_example"
    template_name = 'styleguide/htmx_todo/main.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            "items": self.get_items(),
        }

    def get_items(self):
        return TodoListStore(self.request).get()

    def save_items(self, items):
        TodoListStore(self.request).set(items)

    def update_item(self, item_id, name=None, is_done=None):
        items = self.get_items()
        for item in items:
            if item["id"] == item_id:
                item["name"] = name if name is not None else item["name"]
                item["is_done"] = is_done if is_done is not None else item["is_done"]
                TodoListStore(self.request).set(items)
                return item

    def render_item_response(self, request, item):
        template = ("styleguide/htmx_todo/item_done_oob_swap.html" if item["is_done"]
                    else "styleguide/htmx_todo/item.html")
        context = {
            'item': item,
        }
        return self.render_htmx_partial_response(request, template, context)

    # we can now reference `hq-hx-action="create_new_item"`
    # alongside a `hx-post` to this view URL
    @hq_hx_action('post')
    def create_new_item(self, request, *args, **kwargs):
        items = self.get_items()
        new_item = {
            "id": len(items) + 1,
            "name": _("New Item"),
            "is_done": False,
        }
        items.insert(0, new_item)
        self.save_items(items)
        return self.render_item_response(request, new_item)

    @hq_hx_action('post')
    def edit_item(self, request, *args, **kwargs):
        item = self.update_item(
            int(request.POST['itemId']),
            name=request.POST['newValue'],
        )
        return self.render_item_response(request, item)

    @hq_hx_action('post')
    def mark_item_done(self, request, *args, **kwargs):
        item = self.update_item(
            int(request.POST['itemId']),
            is_done=True,
        )
        return self.render_item_response(request, item)


class TodoListStore(CacheStore):
    """
    CacheStore is a helpful prototyping tool when you need to store
    data on the server side for prototyping HTMX views.

    Caution: Please don't use this for real features.
    """
    slug = 'styleguide-todo-list'
    initial_value = [
        {
            "id": 1,
            "name": "get coat hangers",
            "is_done": False,
        },
        {
            "id": 2,
            "name": "water plants",
            "is_done": False,
        },
        {
            "id": 3,
            "name": "Review PRs",
            "is_done": False,
        },
    ]
