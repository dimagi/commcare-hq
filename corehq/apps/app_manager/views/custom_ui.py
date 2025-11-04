"""
Custom UI views for uploading and managing custom HTML/JS UIs
"""
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.hqmedia.models import CommCareMultimedia
from django.conf import settings
from datetime import datetime
import hashlib
import logging
import json

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
        
        # Use the app's create_mapping method to properly add to multimedia_map
        app.create_mapping(multimedia, multimedia_path, save=False)
        
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


# AI Generation Endpoints

@require_POST
@login_and_domain_required
@require_permission(HqPermissions.edit_apps, login_decorator=None)
def generate_ui_with_ai(request, domain, app_id):
    """
    Generate custom UI using Claude API
    
    POST parameters:
    - message: User's message/request
    - conversation_history: JSON array of previous messages (optional)
    """
    # Check if AI features are enabled
    if not getattr(settings, 'ENABLE_CUSTOM_UI_AI', False):
        return JsonResponse({
            'success': False,
            'message': 'AI features are not enabled'
        }, status=403)
    
    try:
        # Get message from request
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            history_json = data.get('conversation_history', [])
        else:
            user_message = request.POST.get('message', '').strip()
            history_json = request.POST.get('conversation_history', '[]')
            if isinstance(history_json, str):
                history_json = json.loads(history_json)
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'message': 'No message provided'
            }, status=400)
        
        # Get current HTML if modifying
        app = get_app(domain, app_id)
        current_html = _get_current_html(app)
        
        # Build app context
        app_context = _build_app_context(app)
        
        # Generate UI with Claude
        from corehq.apps.app_manager.ai.claude_client import ClaudeUIGenerator
        
        generator = ClaudeUIGenerator()
        result = generator.generate_ui(
            user_message=user_message,
            conversation_history=history_json,
            current_html=current_html,
            app_context=app_context
        )
        
        # Auto-save the generated HTML
        if result['html']:
            save_result = _save_custom_ui_internal(
                request,
                domain, 
                app_id, 
                result['html'],
                filename='index.html'
            )
            
            return JsonResponse({
                'success': True,
                'html': result['html'],
                'explanation': result['explanation'],
                'full_response': result['full_response'],
                'saved': save_result.get('success', False),
                'multimedia_id': save_result.get('multimedia_id'),
                'usage': result['usage']
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Failed to extract HTML from Claude response',
                'full_response': result.get('full_response', '')
            }, status=500)
            
    except ImportError:
        logger.exception("Anthropic package not installed")
        return JsonResponse({
            'success': False,
            'message': 'Anthropic package not installed. Run: pip install anthropic'
        }, status=500)
    except ValueError as e:
        logger.exception("Configuration error")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
    except Exception as e:
        logger.exception(f"Error generating UI for app {app_id}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_and_domain_required
@require_permission(HqPermissions.edit_apps, login_decorator=None)
def get_conversation_context(request, domain, app_id):
    """
    Get context for AI conversation (app structure, current UI, etc.)
    """
    try:
        app = get_app(domain, app_id)
        
        context = {
            'app_name': app.name,
            'app_id': app_id,
            'domain': domain,
            'custom_ui_enabled': app.profile.get('custom_ui_enabled', False),
            'has_current_html': False,
            'app_structure': _build_app_context(app),
        }
        
        # Check if there's current HTML
        if context['custom_ui_enabled']:
            multimedia_id = app.profile.get('custom_ui_multimedia_id')
            if multimedia_id:
                try:
                    CommCareMultimedia.get(multimedia_id)
                    context['has_current_html'] = True
                except:
                    pass
        
        return JsonResponse({
            'success': True,
            'context': context
        })
        
    except Exception as e:
        logger.exception(f"Error getting context for app {app_id}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# Helper functions for AI generation

def _save_custom_ui_internal(request, domain, app_id, html_content, filename='index.html'):
    """
    Internal helper to save HTML (used by AI generation and manual upload)
    """
    try:
        app = get_app(domain, app_id)
        file_hash = hashlib.md5(html_content.encode('utf-8')).hexdigest()
        multimedia_id = f"custom_ui_{filename}"
        
        try:
            multimedia = CommCareMultimedia.get_by_data_id(app._id, multimedia_id)
        except:
            multimedia = CommCareMultimedia()
            multimedia.file_hash = file_hash
            multimedia.valid_domains = [domain]
            multimedia.owners = [domain]
        
        multimedia.attach_data(
            html_content.encode('utf-8'),
            original_filename=filename,
            username=request.user.username if request else 'ai-generated'
        )
        multimedia.save()
        
        multimedia_path = f'custom_ui/{filename}'
        app.create_mapping(multimedia, multimedia_path, save=False)
        
        if not app.profile:
            app.profile = {}
        
        app.profile['custom_ui_enabled'] = True
        app.profile['custom_ui_entrypoint'] = multimedia_path
        app.profile['custom_ui_multimedia_id'] = multimedia._id
        app.save()
        
        return {
            'success': True,
            'multimedia_id': multimedia._id
        }
        
    except Exception as e:
        logger.exception("Error in _save_custom_ui_internal")
        return {
            'success': False,
            'message': str(e)
        }


def _get_current_html(app):
    """Get current HTML if it exists"""
    if not app.profile.get('custom_ui_enabled'):
        return None
    
    multimedia_id = app.profile.get('custom_ui_multimedia_id')
    if not multimedia_id:
        return None
    
    try:
        multimedia = CommCareMultimedia.get(multimedia_id)
        html_bytes = multimedia.fetch_attachment(multimedia.file_hash)
        return html_bytes.decode('utf-8')
    except:
        return None


def _build_app_context(app):
    """
    Build context string describing app structure for Claude.
    This helps Claude understand what forms/cases exist.
    """
    context_parts = [f"App Name: {app.name}"]
    
    # Add modules and forms
    if hasattr(app, 'modules') and app.modules:
        context_parts.append("\nModules and Forms:")
        for module in app.modules:
            context_parts.append(f"  - Module: {module.default_name()}")
            if hasattr(module, 'forms'):
                for form in module.forms:
                    form_xmlns = getattr(form, 'xmlns', 'unknown')
                    context_parts.append(
                        f"    - Form: {form.default_name()} "
                        f"(xmlns: {form_xmlns})"
                    )
    
    # Add case types if available
    if hasattr(app, 'get_case_types'):
        try:
            case_types = app.get_case_types()
            if case_types:
                context_parts.append(f"\nCase Types: {', '.join(case_types)}")
        except:
            pass
    
    return "\n".join(context_parts)

