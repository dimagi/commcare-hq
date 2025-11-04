from django.conf import settings
print("ENABLE_CUSTOM_UI_AI:", getattr(settings, 'ENABLE_CUSTOM_UI_AI', 'NOT SET'))
print("ANTHROPIC_API_KEY:", "SET" if getattr(settings, 'ANTHROPIC_API_KEY', None) else "NOT SET")

