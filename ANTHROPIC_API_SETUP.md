# Anthropic API Key Setup (DO NOT COMMIT API KEY)

## ⚠️ Security Notice

**NEVER commit your API key to git!** Follow this guide to set it up securely.

---

## Option 1: Environment Variables in Ubuntu (Recommended)

### For your Ubuntu VM/Container:

1. **Edit your shell profile:**

```bash
# SSH into your Ubuntu VM
nano ~/.bashrc
# or
nano ~/.profile
```

2. **Add these lines at the end:**

```bash
# Anthropic API for CommCare Custom UI
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR-ACTUAL-KEY-HERE"
export ENABLE_CUSTOM_UI_AI="true"
```

3. **Save and reload:**

```bash
source ~/.bashrc
# or
source ~/.profile
```

4. **Verify it's set:**

```bash
echo $ANTHROPIC_API_KEY
# Should print your key
```

5. **Restart CommCare HQ** in the Ubuntu VM

---

## Option 2: Docker Environment File

If running via Docker, create a `.env` file in the commcare-hq directory:

```bash
# commcare-hq/.env (this file is gitignored)
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-ACTUAL-KEY-HERE
ENABLE_CUSTOM_UI_AI=true
```

Then update your `docker-compose.yml` to use it:

```yaml
services:
  web:
    env_file:
      - .env
```

---

## Option 3: Direct in localsettings.py (Local Development Only)

**Only for local development** - modify `docker/localsettings.py`:

```python
# At the end of docker/localsettings.py
ANTHROPIC_API_KEY = 'sk-ant-api03-YOUR-KEY-HERE'
ENABLE_CUSTOM_UI_AI = True
```

**WARNING:** Do NOT commit this file if you add your key!

---

## Verifying the Setup

Once configured, verify in Django shell:

```bash
./manage.py shell
```

```python
from django.conf import settings
print(settings.ANTHROPIC_API_KEY[:20])  # Should print first 20 chars
print(settings.ENABLE_CUSTOM_UI_AI)     # Should print True
```

---

## Getting Your API Key

1. Visit: https://console.anthropic.com/
2. Sign up or log in
3. Go to **API Keys** section
4. Click **Create Key**
5. Copy the key (starts with `sk-ant-api03-`)

---

## Installing the Package

In your Ubuntu VM:

```bash
cd ~/commcare-hq
pip install anthropic
# or if using venv:
source venv/bin/activate
pip install anthropic
```

---

## Current Key Location

Your API key is currently stored in:
- `docker/localsettings.py` (DO NOT COMMIT)

**TODO:** Move it to environment variables following Option 1 or 2 above.

