# Custom UI AI Generation

This module provides AI-powered custom UI generation for CommCare using Claude (Anthropic).

## Setup

### 1. Install the Anthropic Python SDK

```bash
pip install anthropic
```

### 2. Configure API Key

Add your Anthropic API key to your settings. You have two options:

#### Option A: Using localsettings.py (Recommended for local development)

Edit `commcare-hq/localsettings.py` and add:

```python
# Anthropic API Key for Custom UI generation
ANTHROPIC_API_KEY = 'sk-ant-api03-YOUR-KEY-HERE'

# Enable AI features
ENABLE_CUSTOM_UI_AI = True
```

#### Option B: Using Environment Variables

Set environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR-KEY-HERE"
export ENABLE_CUSTOM_UI_AI="true"
```

### 3. Get an API Key

1. Sign up at https://console.anthropic.com/
2. Create a new API key
3. Copy the key (starts with `sk-ant-api03-`)

## Usage

Once configured, navigate to:

**App Builder → Settings → Custom UI**

You'll see a chat interface where you can:
- Describe the UI you want to create
- Iterate on designs through conversation
- Preview changes in real-time
- Use quick-start templates

## Cost Estimates

Using Claude 3.5 Sonnet:
- **Per generation**: ~$0.03-0.06
- **Light use** (10 generations/day): ~$10-20/month
- **Medium use** (50 generations/day): ~$50-100/month

## Features

- **Natural language interface**: Describe what you want in plain English
- **Iterative design**: Build on previous generations
- **Auto-save**: Generated UIs are automatically saved to your app
- **Live preview**: See changes immediately in the app preview
- **Context-aware**: Claude knows about your app's forms and case types
- **Quick starts**: Pre-built templates for common use cases

## Architecture

```
User Message
    ↓
ClaudeUIGenerator (claude_client.py)
    ↓
Claude API (Anthropic)
    ↓
Generated HTML
    ↓
Auto-save (custom_ui.py)
    ↓
Preview Refresh
```

## Troubleshooting

### "API key not configured" error

Make sure you've set `ANTHROPIC_API_KEY` in your settings or environment variables.

### "anthropic package not installed" error

Run: `pip install anthropic`

### "AI features are not enabled" error

Set `ENABLE_CUSTOM_UI_AI = True` in your settings.

### Chat interface doesn't appear

Check that the template is including the chat interface:
- The flag `ENABLE_CUSTOM_UI_AI` needs to be passed to the template context
- If disabled, you'll see the manual upload interface instead

## Development

The AI generation system consists of:

### Backend:
- `ai/claude_client.py` - Claude API client
- `views/custom_ui.py` - Generation endpoints
- System prompt defines Claude's behavior

### Frontend:
- `templates/.../custom_ui_chat.html` - Chat UI
- `static/.../chat_viewmodel.js` - Knockout.js ViewModel

### Configuration:
- `urls.py` - Route definitions
- `localsettings.py` - API key and feature flags

## System Prompt

The system prompt in `claude_client.py` teaches Claude about:
- CommCareAPI bridge methods
- Mobile-first design patterns
- Single-file HTML requirements
- Error handling and loading states

You can customize the prompt to change Claude's behavior.

## Security

- API key stored server-side only
- HTML generated in isolated preview iframe
- Same security model as Phase 2 (manual upload)
- User permissions required to access

