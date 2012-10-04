from django import forms
from django.forms.util import ErrorList
from django.utils.safestring import mark_safe
from dimagi.utils.decorators.memoized import memoized

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
    def editable_item_display_columns(self):
        """
            Returns a list of properties to display as the columns for the editable row.
            Be aware of order.
        """
        return NotImplementedError

    @property
    def as_row(self):
        row = []
        for key in self.editable_item_display_columns:
            property = getattr(self, key)
            row.append(self.editable_item_format_displayed_property(key, property))
        row.append(self.editable_item_button)
        return row

    def editable_item_format_displayed_property(self, key, property):
        return property

    def editable_item_update(self, overwrite=True, **kwargs):
        """
            Update the existing item from the form parameters here.
        """
        raise NotImplementedError

    @classmethod
    def is_editable_item_valid(cls, existing_item=None, **kwargs):
        return True

    @classmethod
    def editable_item_create(cls, overwrite=True, **kwargs):
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
        if item_id and data is None:
            data=self.editable_item._doc
        if not issubclass(self._item_class, InterfaceEditableItemMixin):
            raise ValueError("_item_class should have the InterfaceEditableItemMixin")

        super(InterfaceEditableItemForm, self).__init__(data, files, auto_id, prefix, initial,
            error_class, label_suffix, empty_permitted)

    @property
    @memoized
    def editable_item(self):
        if self.item_id:
            return self._item_class.get(self.item_id)
        return None

    def clean(self):
        cleaned_data = super(InterfaceEditableItemForm, self).clean()
        if not self._item_class.is_editable_item_valid(self.editable_item, **cleaned_data):
            raise forms.ValidationError("This item already exists.")
        return cleaned_data

    def save(self):
        if self.editable_item:
            item = self.editable_item
            item.editable_item_update(**self.cleaned_data)
        else:
            item = self._item_class.editable_item_create(**self.cleaned_data)
        return [item.as_row]
