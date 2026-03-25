# VitalNet 🩺

VitalNet is a high-performance AI-driven clinical triage and briefing platform designed for rural health workers (ASHAs) and doctors. It leverage machine learning and large language models to provide instant diagnostic insights and patient briefings.

## 🚀 Features

- **Local ML Triage**: Uses a `HistGradientBoostingClassifier` to predict urgency (EMERGENCY, URGENT, ROUTINE) locally on the backend.
- **SHAP Risk Explanations**: Provides per-patient "Risk Drivers" identifying exactly which vitals or symptoms triggered the triage level.
- **AI Clinical Briefings**: Generates detailed clinical context (differential diagnoses, red flags, and actions) using Groq's Llama models with a resilient fallback chain.
- **Priority Dashboard**: A real-time Doctor's dashboard that auto-refreshes and sorts cases by medical severity.
- **SaaS-tier UI**: Polished Tailwind v4 interface with a premium solid elevation system and interactive clinical inputs.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- **Python 3.13** (strictly required for classifier compatibility)
- **Node.js** (v18+ recommended)
- **Groq API Key** (for clinical briefings)

### 2. Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables. Create a `.env` file in `backend/`:
   ```env
   GROQ_API_KEY=your_key_here
   DATABASE_URL=sqlite:///./vitalnet.db
   ```
5. Run the server:
   ```bash
   python -m uvicorn main:app --reload --port 8000
   ```
   *The API will be available at http://localhost:8000. Check http://localhost:8000/api/health to verify.*

### 3. Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Configure environment variables. Create a `.env` file in `frontend/`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   ```
4. Run the development server:
   ```bash
   npm run dev
   ```
   *The app will be available at http://localhost:5173.*

---

## 🚢 Deployment

### Railway (Backend)
- The backend is pre-configured with `Procfile`, `railway.toml`, and `runtime.txt`.
- Set your `GROQ_API_KEY` in the Railway dashboard environment variables.

### Vercel (Frontend)
- The frontend includes `vercel.json` for SPA routing.
- Set `VITE_API_BASE_URL` to your production backend URL in the Vercel dashboard.

---

## 📝 License
This project is part of a 24-hour rapid development sprint. Built with 🩺 by Antigravity.

# VitalNet CI Trigger v2
