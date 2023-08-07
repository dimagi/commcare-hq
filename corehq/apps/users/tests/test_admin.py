from django.test import SimpleTestCase

from corehq.apps.users.admin import CustomUserAdmin


class CustomUserAdminTest(SimpleTestCase):

    def test_fieldsets(self):
        """
        Test that the value of CustomUserAdmin.fieldsets,
        dynamically calculated by removing fields from UserAdmin,
        matches hard-coded value.

        This will alert us of any changes to Django's own UserAdmin that affect this,
        and allow us to make any changes necessitated by that.
        This is probably over-careful, but might help us quickly avoid a surprise.

        """
        self.assertEqual(CustomUserAdmin.fieldsets, (
            (None, {'fields': ('username', 'password')}),
            ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
            ('Permissions', {'fields': ('is_active', 'groups', 'user_permissions')}),
            ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ))
