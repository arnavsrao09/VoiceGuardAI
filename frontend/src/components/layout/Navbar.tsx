import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Menu, X, Activity, Users, Bell, LogOut, Building2 } from 'lucide-react';
import { apiFetch, getAuthToken, removeAuthToken } from '../../lib/api';

const navLinks = [
  { to: '/dashboard', label: 'Dashboard', icon: Activity },
  { to: '/keys', label: 'API Keys', icon: Shield },
  { to: '/speakers', label: 'Speaker Profiles', icon: Users },
  { to: '/alerts', label: 'Alerts', icon: Bell },
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
          // Token invalid or expired
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
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="relative w-9 h-9 rounded-lg bg-gradient-to-br from-[var(--color-accent-primary)] to-[var(--color-accent-purple)] flex items-center justify-center shadow-lg shadow-[var(--color-accent-primary-glow)] group-hover:shadow-xl group-hover:shadow-[var(--color-accent-primary-glow)] transition-shadow duration-300">
            <Shield className="w-5 h-5 text-white" strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold font-[var(--font-heading)] text-[var(--color-sentinel-text)] tracking-tight">
            Voice<span className="text-[var(--color-accent-primary)]">GuardAI</span>
          </span>
        </Link>

        {/* Desktop Links */}
        {!isLanding && !isAuth && (
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map(({ to, label, icon: Icon }) => {
              const active = location.pathname === to;
              return (
                <Link
                  key={to}
                  to={to}
                  className={`relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    active
                      ? 'text-[var(--color-accent-primary)]'
                      : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                  {active && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute inset-0 rounded-lg bg-[var(--color-accent-primary-dim)] border border-[var(--color-accent-primary)]/20"
                      style={{ zIndex: -1 }}
                      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    />
                  )}
                </Link>
              );
            })}
          </div>
        )}

        {/* CTA / Mobile Toggle */}
        <div className="flex items-center gap-3">
          {!hasToken ? (
            <Link
              to="/auth"
              className="hidden sm:inline-flex items-center gap-2 px-5 py-2 rounded-full bg-gradient-to-r from-[#0b3332] to-[#261747] text-white border border-[#00e5c8]/30 hover:border-[#00e5c8]/70 hover:from-[#0f403f] hover:to-[#321f5c] text-sm font-semibold shadow-md hover:scale-105 transition-all duration-200"
              style={{ boxShadow: '0 4px 20px rgba(0, 229, 200, 0.12)' }}
            >
              <Activity className="w-4 h-4 text-[var(--color-accent-primary)]" />
              Organization Login
            </Link>
          ) : (
            <div className="hidden sm:flex items-center gap-3">
              {orgName && (
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--color-sentinel-surface-2)] border border-[var(--color-sentinel-border)] text-xs font-medium text-[var(--color-sentinel-text-muted)]">
                  <Building2 className="w-3.5 h-3.5 text-[var(--color-accent-primary)]" />
                  {orgName}
                </div>
              )}
              <button
                onClick={handleLogout}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-red-500/40 text-red-400 text-xs font-semibold hover:bg-red-500/10 transition-all duration-200"
              >
                <LogOut className="w-3.5 h-3.5" />
                Log Out
              </button>
            </div>
          )}

          {/* Mobile hamburger */}
          {!isLanding && !isAuth && (
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden w-9 h-9 rounded-lg flex items-center justify-center text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)] transition-colors"
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Mobile Dropdown */}
      <AnimatePresence>
        {mobileOpen && !isLanding && !isAuth && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden overflow-hidden bg-[var(--color-sentinel-surface)]/95 backdrop-blur-xl border-b border-[var(--color-sentinel-border)]"
          >
            <div className="px-6 py-3 flex flex-col gap-1">
              {navLinks.map(({ to, label, icon: Icon }) => {
                const active = location.pathname === to;
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                      active
                        ? 'text-[var(--color-accent-primary)] bg-[var(--color-accent-primary-dim)]'
                        : 'text-[var(--color-sentinel-text-muted)] hover:text-[var(--color-sentinel-text)] hover:bg-[var(--color-sentinel-surface-2)]'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                  </Link>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}
