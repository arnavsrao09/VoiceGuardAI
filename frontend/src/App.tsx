import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Navbar from './components/layout/Navbar';
import AlertsPage from './pages/AlertsPage';
import ApiKeysPage from './pages/ApiKeysPage';
import AuthPage from './pages/AuthPage';
import DashboardPage from './pages/DashboardPage';
import LandingPage from './pages/LandingPage';
import PrivacyPage from './pages/PrivacyPage';
import SettingsPage from './pages/SettingsPage';
import SpeakerProfilesPage from './pages/SpeakerProfilesPage';

function AppRoutes() {
  const location = useLocation();

  const pagesWithSidebarPadding = [
    '/keys',
    '/speakers',
    '/alerts',
    '/settings',
    '/privacy',
  ];

  const needsSidebarPadding = pagesWithSidebarPadding.includes(location.pathname);

  return (
    <div className={needsSidebarPadding ? 'md:pl-64' : ''}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/keys"
          element={
            <ProtectedRoute>
              <ApiKeysPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/speakers"
          element={
            <ProtectedRoute>
              <SpeakerProfilesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/alerts"
          element={
            <ProtectedRoute>
              <AlertsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/privacy"
          element={
            <ProtectedRoute>
              <PrivacyPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      {/* Animated background mesh */}
      <div className="gradient-mesh" />

      {/* Navigation */}
      <Navbar />

      {/* Routes */}
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;