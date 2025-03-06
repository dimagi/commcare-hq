import pytest
from django.test import RequestFactory
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, HqPermissions, UserRole
from corehq.tabs.tabclasses import CampaignDashboardTab


@pytest.fixture(scope="module")
def domain_setup():
    domain_name = 'test-domain'
    domain = Domain.get_or_create_with_name(domain_name)
    
    # Create admin user
    admin_username = 'admin@example.com'
    admin_password = 'adminpassword'
    admin_user = WebUser.create(domain_name, admin_username, admin_password, None, None)
    admin_user.is_superuser = True
    admin_user.save()
    
    # Create a role with campaign dashboard permission
    role_with_permission = UserRole.create(
        domain_name,
        'Campaign Dashboard Role',
        permissions=HqPermissions(
            view_campaign_dashboard=True
        )
    )
    
    # Create a role without campaign dashboard permission
    role_without_permission = UserRole.create(
        domain_name,
        'No Campaign Dashboard Role',
        permissions=HqPermissions(
            view_campaign_dashboard=False
        )
    )
    
    # Create user with permission
    user_with_permission_username = 'user_with_permission@example.com'
    user_with_permission_password = 'password'
    user_with_permission = WebUser.create(
        domain_name,
        user_with_permission_username,
        user_with_permission_password,
        None,
        None
    )
    user_with_permission.set_role(domain_name, role_with_permission.get_qualified_id())
    user_with_permission.save()
    
    # Create user without permission
    user_without_permission_username = 'user_without_permission@example.com'
    user_without_permission_password = 'password'
    user_without_permission = WebUser.create(
        domain_name,
        user_without_permission_username,
        user_without_permission_password,
        None,
        None
    )
    user_without_permission.set_role(domain_name, role_without_permission.get_qualified_id())
    user_without_permission.save()
    
    # Create request factory
    factory = RequestFactory()
    
    yield (
        domain_name, 
        domain, 
        admin_user, 
        admin_username, 
        admin_password,
        user_with_permission, 
        user_with_permission_username, 
        user_with_permission_password,
        user_without_permission, 
        user_without_permission_username, 
        user_without_permission_password,
        role_with_permission,
        role_without_permission,
        factory
    )
    
    # Cleanup
    user_with_permission.delete(domain_name, deleted_by=None)
    user_without_permission.delete(domain_name, deleted_by=None)
    admin_user.delete(domain_name, deleted_by=None)
    role_with_permission.delete()
    role_without_permission.delete()
    domain.delete()


class TestCampaignDashboardPermissions:
    """Test cases for the Campaign Dashboard permissions"""

    def test_admin_can_access_dashboard(self, domain_setup):
        """Test that an admin user can access the dashboard"""
        domain_name, _, _, admin_username, admin_password, _, _, _, _, _, _, _, _, _ = domain_setup
        client = self._get_client(admin_username, admin_password)
        
        url = reverse('campaign_dashboard', args=[domain_name])
        response = client.get(url)
        assert response.status_code == 200

    def test_user_with_permission_can_access_dashboard(self, domain_setup):
        """Test that a user with the view_campaign_dashboard permission can access the dashboard"""
        domain_name, _, _, _, _, _, user_with_permission_username, user_with_permission_password, _, _, _, _, _, _ = domain_setup
        client = self._get_client(user_with_permission_username, user_with_permission_password)
        
        url = reverse('campaign_dashboard', args=[domain_name])
        response = client.get(url)
        assert response.status_code == 200

    def test_user_without_permission_cannot_access_dashboard(self, domain_setup):
        """Test that a user without the view_campaign_dashboard permission cannot access the dashboard"""
        domain_name, _, _, _, _, _, _, _, _, user_without_permission_username, user_without_permission_password, _, _, _ = domain_setup
        client = self._get_client(user_without_permission_username, user_without_permission_password)
        
        url = reverse('campaign_dashboard', args=[domain_name])
        response = client.get(url)
        # Should redirect to login or permission denied page
        assert response.status_code != 200

    def test_tab_visibility_for_admin(self, domain_setup):
        """Test that the Campaign Dashboard tab is visible for admin users"""
        domain_name, domain, admin_user, _, _, _, _, _, _, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = admin_user
        request.project = domain
        
        tab = CampaignDashboardTab(request)
        assert tab.is_viewable is True

    def test_tab_visibility_for_user_with_permission(self, domain_setup):
        """Test that the Campaign Dashboard tab is visible for users with the view_campaign_dashboard permission"""
        domain_name, domain, _, _, _, user_with_permission, _, _, _, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = user_with_permission
        request.project = domain
        
        tab = CampaignDashboardTab(request)
        assert tab.is_viewable is True

    def test_tab_visibility_for_user_without_permission(self, domain_setup):
        """Test that the Campaign Dashboard tab is not visible for users without the view_campaign_dashboard permission"""
        domain_name, domain, _, _, _, _, _, _, user_without_permission, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = user_without_permission
        request.project = domain
        
        tab = CampaignDashboardTab(request)
        assert tab.is_viewable is False

    def test_dashboard_tile_visibility_for_admin(self, domain_setup):
        """Test that the Campaign Dashboard tile is visible for admin users"""
        from corehq.apps.dashboard.views import _get_default_tiles
        
        domain_name, domain, admin_user, _, _, _, _, _, _, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = admin_user
        request.project = domain
        
        tiles = _get_default_tiles(request)
        campaign_dashboard_tile = next((tile for tile in tiles if tile.slug == 'campaign_dashboard'), None)
        
        assert campaign_dashboard_tile is not None
        assert campaign_dashboard_tile.is_visible is True

    def test_dashboard_tile_visibility_for_user_with_permission(self, domain_setup):
        """Test that the Campaign Dashboard tile is visible for users with the view_campaign_dashboard permission"""
        from corehq.apps.dashboard.views import _get_default_tiles
        
        domain_name, domain, _, _, _, user_with_permission, _, _, _, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = user_with_permission
        request.project = domain
        
        tiles = _get_default_tiles(request)
        campaign_dashboard_tile = next((tile for tile in tiles if tile.slug == 'campaign_dashboard'), None)
        
        assert campaign_dashboard_tile is not None
        assert campaign_dashboard_tile.is_visible is True

    def test_dashboard_tile_visibility_for_user_without_permission(self, domain_setup):
        """Test that the Campaign Dashboard tile is not visible for users without the view_campaign_dashboard permission"""
        from corehq.apps.dashboard.views import _get_default_tiles
        
        domain_name, domain, _, _, _, _, _, _, user_without_permission, _, _, _, _, factory = domain_setup
        
        request = factory.get('/')
        request.domain = domain_name
        request.couch_user = user_without_permission
        request.project = domain
        
        tiles = _get_default_tiles(request)
        campaign_dashboard_tile = next((tile for tile in tiles if tile.slug == 'campaign_dashboard'), None)
        
        assert campaign_dashboard_tile is not None
        assert campaign_dashboard_tile.is_visible is False
        
    def _get_client(self, username, password):
        from django.test import Client
        client = Client()
        client.login(username=username, password=password)
        return client 