"""
Custom UI views for uploading and managing custom HTML/JS UIs
"""
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.hqmedia.models import CommCareMultimedia
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)


@require_POST
@login_and_domain_required
@require_permission(HqPermissions.edit_apps, login_decorator=None)
def save_custom_ui(request, domain, app_id):
    """
    Save custom UI HTML file to app as multimedia attachment.
    
    POST parameters:
    - file: HTML file upload
    OR
    - html_content: HTML content as string (JSON)
    - filename: (optional) filename, defaults to 'index.html'
    """
    try:
        import json
        
        # Get HTML content from file upload or POST data
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            html_content = uploaded_file.read().decode('utf-8')
            filename = uploaded_file.name
        else:
            # Check if JSON body
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                html_content = data.get('html_content')
                filename = data.get('filename', 'index.html')
            else:
                html_content = request.POST.get('html_content') or request.POST.get('html')
                filename = request.POST.get('filename', 'index.html')
        
        if not html_content:
            return JsonResponse({
                'success': False,
                'message': 'No HTML content provided'
            }, status=400)
        
        # Get the app
        app = get_app(domain, app_id)
        
        # Create file hash for multimedia ID
        file_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
        
        # Create or update multimedia object
        multimedia_id = f"custom_ui_{filename}"
        
        # Try to find existing multimedia with this ID
        try:
            multimedia = CommCareMultimedia.get_by_data_id(
                app._id,
                multimedia_id
            )
        except:
            multimedia = CommCareMultimedia()
            multimedia.file_hash = file_hash
            multimedia.valid_domains = [domain]
            multimedia.owners = [domain]
        
        # Attach the HTML data
        multimedia.attach_data(
            html_content.encode('utf-8'),
            original_filename=filename,
            username=request.user.username
        )
        multimedia.save()
        
        # Add multimedia to app's multimedia_map
        # The path in CCZ will be custom_ui/filename
        multimedia_path = f'custom_ui/{filename}'
        if not app.multimedia_map:
            app.multimedia_map = {}
        
        from corehq.apps.hqmedia.models import HQMediaMapItem
        app.multimedia_map[multimedia_path] = HQMediaMapItem(
            multimedia_id=multimedia._id,
            unique_id=multimedia._id,
            version=1,
        )
        
        # Update app profile to enable custom UI
        if not app.profile:
            app.profile = {}
        
        app.profile['custom_ui_enabled'] = True
        app.profile['custom_ui_entrypoint'] = multimedia_path
        app.profile['custom_ui_multimedia_id'] = multimedia._id
        app.save()
        
        logger.info(
            f"Custom UI saved for app {app_id} in domain {domain}. "
            f"Multimedia ID: {multimedia._id}, File: {filename}"
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Custom UI uploaded successfully: {filename}',
            'multimedia_id': multimedia._id,
            'entrypoint': app.profile['custom_ui_entrypoint']
        })
        
    except Exception as e:
        logger.exception(f"Error saving custom UI for app {app_id}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_and_domain_required
@require_permission(HqPermissions.edit_apps, login_decorator=None)
def get_custom_ui_status(request, domain, app_id):
    """
    Get current custom UI status for an app
    """
    try:
        app = get_app(domain, app_id)
        
        custom_ui_enabled = app.profile.get('custom_ui_enabled', False)
        custom_ui_entrypoint = app.profile.get('custom_ui_entrypoint', None)
        multimedia_id = app.profile.get('custom_ui_multimedia_id', None)
        
        return JsonResponse({
            'success': True,
            'enabled': custom_ui_enabled,
            'entrypoint': custom_ui_entrypoint,
            'multimedia_id': multimedia_id
        })
    except Exception as e:
        logger.exception(f"Error getting custom UI status for app {app_id}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@require_POST
@login_and_domain_required
@require_permission(HqPermissions.edit_apps, login_decorator=None)
def disable_custom_ui(request, domain, app_id):
    """
    Disable custom UI for an app (doesn't delete the files)
    """
    try:
        app = get_app(domain, app_id)
        
        if app.profile:
            app.profile['custom_ui_enabled'] = False
        
        app.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Custom UI disabled'
        })
    except Exception as e:
        logger.exception(f"Error disabling custom UI for app {app_id}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)

