from django import forms
from django.forms.util import ErrorList
from django.utils.safestring import mark_safe

class InterfaceEditableItemMixin(object):
    """
        Use this mixin for any couch models that you plan on creating an admin / editable
        interface for. See the adm app in dimagi/corehq-src for example usage.
    """

    @property
    def editable_item_button(self):
        """
            Use this to format the editable item button.
        """
        return NotImplementedError

    @property
    def row_columns(self):
        """
            Returns a list of properties to display as the columns for the editable row.
            Be aware of order.
        """
        return NotImplementedError

    @property
    def as_row(self):
        row = []
        for key in self.row_columns:
            property = getattr(self, key)
            row.append(self.format_property(key, property))
        row.append(mark_safe(self.editable_item_button))
        return row

    def format_property(self, key, property):
        return property

    def update_item(self, overwrite=True, **kwargs):
        """
            Update the existing item from the form parameters here.
        """
        raise NotImplementedError

    @classmethod
    def create_item(cls, overwrite=True, **kwargs):
        """
            Create an existing item from the form parameters here.
            You may use this method to prevent duplicates items, if that is your intent.
            This should return the created item.
        """
        raise NotImplementedError


class InterfaceEditableItemForm(forms.Form):
    """
        A generic form for updating a couch model with the InterfaceEditableItemMixin
    """
    _item_class = None

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None,
                 initial=None, error_class=ErrorList, label_suffix=':',
                 empty_permitted=False, item_id=None):
        self.item_id = item_id
        if not issubclass(self._item_class, InterfaceEditableItemMixin):
            raise ValueError("_item_class should have the InterfaceEditableItemMixin")

        super(InterfaceEditableItemForm, self).__init__(data, files, auto_id, prefix, initial,
            error_class, label_suffix, empty_permitted)

    def update(self, item):
        item.update_item(**self.cleaned_data)
        return [item.as_row]

    def save(self):
        item = self._item_class.create_item(**self.cleaned_data)
        return [item.as_row]
