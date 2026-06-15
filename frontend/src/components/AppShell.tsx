import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="top-nav">
        <NavLink to="/demo" className="brand-link">
          <span className="brand-mark">C</span>
          <span>
            <strong>CompEye Agent</strong>
            <small>AI 竞品分析工作台</small>
          </span>
        </NavLink>
        <nav className="nav-links" aria-label="Primary">
          <NavLink to="/overview">概览</NavLink>
        </nav>
        <span className="live-badge">Live</span>
      </header>
      <main>{children}</main>
    </div>
  );
}
