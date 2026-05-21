import { lazy, Suspense, useEffect } from "react";
import { AuthProvider, useAuth } from "./store/authStore";
import { RouteGuard } from "./components/RouteGuard";
import ToastProvider from "./components/ToastProvider";
import { UpdatePrompt } from "./components/UpdatePrompt";
import ErrorBoundary from "./components/ErrorBoundary";
import { purgeExpiredDrafts } from "./hooks/useDraftSave";

// ROOT-PERF-001: lazy-load role panels instead of shipping all code upfront.
const ASHAPanel = lazy(() => import("./panels/ASHAPanel"));
const DoctorPanel = lazy(() => import("./panels/DoctorPanel"));
const AdminPanel = lazy(() => import("./panels/AdminPanel"));

function PanelFallback() {
	return (
		<div className="min-h-screen bg-bg flex items-center justify-center">
			<div className="text-center">
				<div className="w-8 h-8 border-3 border-forest border-t-transparent rounded-full animate-spin mx-auto mb-4" />
				<p className="text-sm text-text3">Loading panel...</p>
			</div>
		</div>
	);
}

function AppInner() {
	const { profile, signOut } = useAuth();

	if (profile && profile.is_active === false) {
		return (
			<div className="min-h-screen bg-bg flex items-center justify-center">
				<div className="text-center animate-fade-up">
					<p className="text-text font-medium">Account deactivated</p>
					<p className="text-text3 text-sm mt-1">Contact your administrator.</p>
					<button
						onClick={signOut}
						className="mt-4 text-sm text-text2 hover:text-terra transition-colors"
					>
						Sign out
					</button>
				</div>
			</div>
		);
	}

	if (profile?.role === "admin") {
		return (
			<Suspense fallback={<PanelFallback />}>
				<AdminPanel />
			</Suspense>
		);
	}

	if (profile?.role === "doctor") {
		return (
			<Suspense fallback={<PanelFallback />}>
				<DoctorPanel />
			</Suspense>
		);
	}

	if (profile?.role === "asha_worker") {
		return (
			<Suspense fallback={<PanelFallback />}>
				<ASHAPanel />
			</Suspense>
		);
	}

	return null;
}

export default function App() {
	useEffect(() => {
		purgeExpiredDrafts().catch((err) => {
			console.error("Failed to purge expired drafts:", err);
		});
	}, []);

	return (
		<ErrorBoundary>
			<AuthProvider>
				<ToastProvider>
					<UpdatePrompt />
					<RouteGuard>
						<AppInner />
					</RouteGuard>
				</ToastProvider>
			</AuthProvider>
		</ErrorBoundary>
	);
}
