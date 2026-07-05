#!/usr/bin/env bash
# VitalNet — one-command local setup.
#
# Installs backend + frontend dependencies and walks you through creating
# backend/.env.local and frontend/.env.local from the .env.example templates.
# Both files are gitignored — nothing this script writes is ever committed.
# Safe to re-run: it never overwrites an .env.local that already exists, and
# skips dependency installs that are already done.
#
# Usage: ./setup.sh
# Requires: bash, python3 (3.11+), node/npm (v20+). On Windows, run this from
# WSL or Git Bash — a native PowerShell port is not provided.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")

say() { echo "${BOLD}==> $1${RESET}"; }

# Prompts for a value and appends/updates KEY=value in the given env file.
# Secret values are read with -s (no echo). Leaving input blank keeps
# whatever's already there (usually the .env.example placeholder).
prompt_env_var() {
  local file="$1" key="$2" description="$3" secret="${4:-false}"
  local current
  current=$(grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true)
  # .env.example's placeholders (your_anon_key_here, https://your-ref...,
  # etc.) all contain "your" — treat those the same as genuinely empty so a
  # fresh copy of the template still prompts instead of silently keeping a
  # placeholder. A real re-run (a genuine key already saved) won't match this.
  if [ -n "$current" ] && [[ "$current" != *your* ]]; then
    return  # already set to a real value (e.g. re-running setup) — don't ask again
  fi

  echo "  ${description}"
  local value=""
  if [ "$secret" = "true" ]; then
    read -r -s -p "  ${key} (input hidden, press Enter to skip): " value
    echo
  else
    read -r -p "  ${key} (press Enter to skip): " value
  fi

  if [ -n "$value" ]; then
    if grep -qE "^${key}=" "$file" 2>/dev/null; then
      # Escape & and | for sed's replacement string
      local escaped
      escaped=$(printf '%s' "$value" | sed -e 's/[&|]/\\&/g')
      sed -i.bak -E "s|^${key}=.*|${key}=${escaped}|" "$file" && rm -f "${file}.bak"
    else
      echo "${key}=${value}" >> "$file"
    fi
  fi
}

# ── Backend ──────────────────────────────────────────────────────────────

say "Setting up backend (Python)"
cd backend

if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo ""
  say "backend/.env.local created — let's fill in the required values"
  echo "  (Everything below stays local — .env.local is gitignored and is"
  echo "   never committed. Skip anything optional by pressing Enter.)"
  echo ""
  prompt_env_var .env.local SUPABASE_URL "Supabase project URL (Project Settings > API)"
  prompt_env_var .env.local SUPABASE_ANON_KEY "Supabase anon/public key" true
  prompt_env_var .env.local SUPABASE_JWT_SECRET "Supabase JWT secret (Project Settings > API > JWT Settings)" true
  prompt_env_var .env.local SUPABASE_SERVICE_ROLE_KEY "Supabase service_role key (admin-only operations)" true
  prompt_env_var .env.local GROQ_API_KEY "Groq API key — required, primary LLM + voice transcription tier" true
  echo ""
  echo "  Optional (all safe to skip and add later — see backend/.env.example):"
  prompt_env_var .env.local GEMINI_API_KEY "Gemini API key — optional LLM fallback tiers 3/4" true
  prompt_env_var .env.local SARVAM_API_KEY "Sarvam AI API key — optional voice-transcription fallback" true
else
  echo "  backend/.env.local already exists — leaving it untouched."
fi

deactivate
cd ..

# ── Frontend ─────────────────────────────────────────────────────────────

say "Setting up frontend (Node)"
cd frontend
npm install --silent

if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo ""
  say "frontend/.env.local created — let's fill in the required values"
  prompt_env_var .env.local VITE_SUPABASE_URL "Same Supabase project URL as above"
  prompt_env_var .env.local VITE_SUPABASE_ANON_KEY "Same Supabase anon key as above" true
  sed -i.bak -E "s|^VITE_API_BASE_URL=.*|VITE_API_BASE_URL=http://localhost:8000|" .env.local && rm -f .env.local.bak
  echo "  VITE_API_BASE_URL set to http://localhost:8000 (change it in frontend/.env.local for a hosted backend)."
  echo "  VITE_VAPID_PUBLIC_KEY left blank — optional, only needed for Web Push."
else
  echo "  frontend/.env.local already exists — leaving it untouched."
fi
cd ..

echo ""
say "Setup complete."
cat <<'EOF'

Still needed before the app is fully functional (can't be automated — these
are decisions/resources only you control):
  1. Run every migration in backend/supabase/migrations/ (in numeric order)
     against your Supabase project's SQL editor, or via the Supabase CLI.
  2. (Optional) seed test accounts — see Context/test_credentials.md and
     backend/seed_user.py.

To run it:
  Backend:  cd backend && source venv/bin/activate && python -m uvicorn app.main:app --reload --port 8000
  Frontend: cd frontend && npm run dev

See README.md for the full walkthrough, or docs/ONBOARDING.md for a
narrated first-time setup including your first change and PR.
EOF
