export default function Footer() {
  return (
    <footer style={{ borderTop: '1px solid var(--color-border)' }} className="px-6 py-6">
      <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        <div className="flex items-center gap-2.5">
          <svg width="18" height="18" viewBox="0 0 30 30" fill="none">
            <rect x="1" y="1" width="28" height="28" rx="6" fill="#15803D" />
            <rect x="5" y="5" width="9" height="9" rx="2" fill="#D97706" opacity="0.9" />
            <rect x="16" y="5" width="9" height="9" rx="2" fill="#22C55E" opacity="0.6" />
          </svg>
          <span className="font-display text-xs tracking-wide" style={{ color: '#94A3B8' }}>BoardGameHub</span>
        </div>
        <span>&copy; 2026</span>
      </div>
    </footer>
  );
}
