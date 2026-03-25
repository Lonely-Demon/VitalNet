# VitalNet 🩺

VitalNet is a high-performance offline-first PWA intended for clinical triage by rural health workers (ASHAs) and PHC doctors. It leverages a rigorous Supabase backend and a multi-tiered LLM architecture to provide instant diagnostic insights in extreme low-resource environments.

## 🚀 Features
- **Offline Reliability**: Full IndexedDB draft pooling and a background queue that syncs automatically when network is restored.
- **Local ML Triage**: Generates EMERGENCY, URGENT, ROUTINE inferences securely in-browser via ONNX WASM.
- **Tiered Clinical Briefings**: Groq Llama 3 70B primary, auto-cascading to Gemini 2.0 Flash fallback architectures for 99.9% uptime.
- **Developer Experience**: Pure FastAPI backend built entirely on dependency injection, strict Zod inputs, structured JSON logging, and fully gated GitHub CI/CD workflows.

---

## 🛠️ Local Development

### 1. Prerequisites
- **Python 3.13** (Required for ONNX classifier compatibility)
- **Node.js** (v20+ recommended)
- **Supabase Local CLI** (`supabase start`)

### 2. Backend Setup
The backend follows a strict enterprise `app/` package architecture.

1. Install dependencies:
   ```bash
   cd backend
   python -m venv venv
   # Windows: venv\\Scripts\\activate | Mac/Linux: source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Set Environment Variables (`backend/.env.local`):
   ```env
   # Local testing keys
   GROQ_API_KEY="..."
   GEMINI_API_KEY="..."
   SUPABASE_URL="..."
   SUPABASE_ANON_KEY="..."
   ```
3. Run the Server:
   ```bash
   python -m uvicorn app.main:app --reload --port 8000
   ```

### 3. Frontend Setup
The frontend is a Vite-powered React 19 SPA utilizing TailwindCSS v4 and Vite-PWA.

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Set Environment Variables (`frontend/.env.local`):
   ```env
   VITE_SUPABASE_URL="..."
   VITE_SUPABASE_ANON_KEY="..."
   VITE_API_BASE_URL="http://localhost:8000"
   ```
3. Run Development Server:
   ```bash
   npm run dev
   ```

---

## 🔒 Branching Workflow & CI/CD
This repository employs **Strict Branch Protection**:
1. You cannot push to `main` directly.
2. Cut a feature branch (`git checkout -b feature/your-name`), make changes, and push.
3. Open a Pull Request on GitHub to `main`.
4. GitHub Actions will automatically run `pytest` (Backend) and Vite `build` (Frontend).
5. Once the tests pass **and** secret scanning is cleared, you may squash-merge your branch.

## 📝 License
Proprietary triage platform built for extreme reliability metrics.
