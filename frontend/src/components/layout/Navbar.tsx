import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Menu, X, Activity, Users, Bell, Settings, LogOut, Building2, Lock } from 'lucide-react';
import { apiFetch, getAuthToken, removeAuthToken } from '../../lib/api';
import voiceguardLogo from '../../assets/voiceguard-logo.png';

const navLinks = [
  { to: '/dashboard', label: 'Dashboard', icon: Activity },
  { to: '/keys', label: 'API Keys', icon: Shield },
  { to: '/speakers', label: 'Speaker Profiles', icon: Users },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/privacy', label: 'Privacy', icon: Lock },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const hasToken = !!getAuthToken();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [orgName, setOrgName] = useState<string | null>(null);

  const isLanding = location.pathname === '/';
  const isAuth = location.pathname === '/auth';
  const isAppPage = !isLanding && !isAuth;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (hasToken) {
      apiFetch('/auth/me')
        .then((org) => setOrgName(org.name))
        .catch(() => {
          removeAuthToken();
          setOrgName(null);
        });
    } else {
      setOrgName(null);
    }
  }, [hasToken, location.pathname]);

  const handleLogout = () => {
    removeAuthToken();
    setOrgName(null);
    navigate('/auth');
  };

  /* ─────────────────────────────────────────────
     APP PAGES — DESKTOP SIDEBAR
  ───────────────────────────────────────────── */
  if (isAppPage) {
    return (
      <>
        {/* Desktop Sidebar */}
        <motion.nav
          initial={{ x: -280 }}
          animate={{ x: 0 }}
          transition={{ type: 'spring', stiffness: 120, damping: 20 }}
          className="hidden md:flex fixed top-0 left-0 bottom-0 w-64 z-50 flex-col bg-[var(--color-sentinel-bg)]/95 backdrop-blur-xl border-r border-[var(--color-sentinel-border)]"
        >
          {/* Logo */}
          <div className="px-6 h-20 flex items-center">
            <Link to="/" className="flex items-center gap-2.5 group">
              <img
                src={voiceguardLogo}
                alt=""
                className="w-9 h-9 object-contain"
              />
              <span className="text-lg font-bold font-[var(--font-heading)] text-[var(--color-sentinel-text)] tracking-tight">
                Voice<span className="text-[var(--color-accent-primary)]">GuardAI</span>
              </span>
            </Link>
          </div>

          {/* Navigation */}
          <div className="flex-1 px-4 py-6">
            <p className="px-3 mb-5 text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-[var(--color-sentinel-text-muted)]">
              Navigation
            </p>

            <div className="flex flex-col gap-1 pt-3">
              {navLinks.map(({ to, label, icon: Icon }) => {
                const active = location.pathname === to;

                return (
                  <Link
                    key={to}
                    to={to}
                    className={`relative flex items-center gap-3 px-3.5 py-3 rounded-lg text-[0.9375rem] font-medium transition-all duration-200 ${
                      active
                        ? 'text-[var(--color-accent-primary)]'
                        : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
                    }`}
                  >
                    <Icon className="w-[18px] h-[18px] shrink-0" />
                    {label}

                    {active && (
                      <motion.div
                        layoutId="sidebar-nav-indicator"
                        className="absolute inset-0 rounded-lg bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/20"
                        style={{ zIndex: -1 }}
                        transition={{
                          type: 'spring',
                          stiffness: 300,
                          damping: 30,
                        }}
                      />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Organization + Logout */}
          <div className="px-4 pb-5">
            <div className="border-t border-[var(--color-sentinel-border)] pt-4">
              {orgName && (
                <div className="flex items-center gap-2.5 px-3 py-2.5 mb-2 rounded-lg bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)]">
                  <Building2 className="w-4 h-4 shrink-0 text-[var(--color-accent-primary)]" />
                  <span className="text-sm font-medium text-[var(--color-sentinel-text-muted)] truncate">
                    {orgName}
                  </span>
                </div>
              )}

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-semibold text-red-400 hover:bg-red-500/10 transition-all duration-200"
              >
                <LogOut className="w-[18px] h-[18px]" />
                Log Out
              </button>
            </div>
          </div>
        </motion.nav>

        {/* Mobile Top Bar */}
        <nav className="md:hidden fixed top-0 left-0 right-0 z-50 bg-[var(--color-sentinel-bg)]/90 backdrop-blur-xl border-b border-[var(--color-sentinel-border)]">
          <div className="h-16 px-4 flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2.5">
              <img
                src={voiceguardLogo}
                alt=""
                className="w-9 h-9 object-contain"
              />
              <span className="text-lg font-bold font-[var(--font-heading)] text-[var(--color-sentinel-text)] tracking-tight">
                Voice<span className="text-[var(--color-accent-primary)]">GuardAI</span>
              </span>
            </Link>

            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)] transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>

          <AnimatePresence>
            {mobileOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden bg-[var(--color-sentinel-surface)]/95 backdrop-blur-xl border-b border-[var(--color-sentinel-border)]"
              >
                <div className="px-4 py-3 flex flex-col gap-1">
                  {navLinks.map(({ to, label, icon: Icon }) => {
                    const active = location.pathname === to;

                    return (
                      <Link
                        key={to}
                        to={to}
                        className={`flex items-center gap-3 px-4 py-3 rounded-lg text-[0.9375rem] font-medium transition-colors ${
                          active
                            ? 'text-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)]'
                            : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
                        }`}
                      >
                        <Icon className="w-[18px] h-[18px]" />
                        {label}
                      </Link>
                    );
                  })}

                  {orgName && (
                    <div className="mt-2 pt-3 border-t border-[var(--color-sentinel-border)] flex items-center gap-2.5 px-4 py-3">
                      <Building2 className="w-4 h-4 text-[var(--color-accent-primary)]" />
                      <span className="text-sm text-[var(--color-sentinel-text-muted)] truncate">
                        {orgName}
                      </span>
                    </div>
                  )}

                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <LogOut className="w-[18px] h-[18px]" />
                    Log Out
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </nav>
      </>
    );
  }

  /* ─────────────────────────────────────────────
     LANDING + AUTH — EXISTING TOP NAVBAR
  ───────────────────────────────────────────── */
  return (
    <motion.nav
      initial={{ y: -80 }}
      animate={{ y: 0 }}
      transition={{ type: 'spring', stiffness: 120, damping: 20 }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[var(--color-sentinel-bg)]/80 backdrop-blur-xl border-b border-[var(--color-sentinel-border)]'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <img
            src={voiceguardLogo}
            alt=""
            className="w-9 h-9 object-contain"
          />
          <span className="text-lg font-bold font-[var(--font-heading)] text-[var(--color-sentinel-text)] tracking-tight">
            Voice<span className="text-[var(--color-accent-primary)]">GuardAI</span>
          </span>
        </Link>

        {/* CTA */}
        <div className="flex items-center gap-3">
          {!hasToken ? (
            <Link
              to="/auth"
              className="hidden sm:inline-flex items-center gap-2 px-5 py-2 rounded-full bg-gradient-to-r from-[var(--color-accent-primary)]/80 to-[var(--color-accent-purple)]/80 text-white text-sm font-semibold hover:brightness-105 transition-all duration-200"
            >
              <Activity className="w-4 h-4" />
              Organization Login
            </Link>
          ) : (
            <div className="hidden sm:flex items-center gap-3">
              {orgName && (
                <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-[0.8125rem] font-medium text-[var(--color-sentinel-text-muted)]">
                  <Building2 className="w-4 h-4 text-[var(--color-accent-primary)]" />
                  {orgName}
                </div>
              )}

              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-red-500/40 text-red-400 text-[0.8125rem] font-semibold hover:bg-red-500/10 transition-all duration-200"
              >
                <LogOut className="w-4 h-4" />
                Log Out
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.nav>
  );
}