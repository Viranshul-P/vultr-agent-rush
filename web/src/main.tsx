import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { BarChart3, BookOpen, Home as HomeIcon, Inbox as InboxIcon, Landmark, Menu, Monitor, Moon, Sun, Swords, X } from "lucide-react";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./styles.css";
import { api } from "./api";
import { Logo, ToastProvider, ease } from "./ui";
import { Home } from "./pages/Home";
import { Inbox } from "./pages/Inbox";
import { InvoiceDetail } from "./pages/InvoiceDetail";
import { RedTeam } from "./pages/RedTeam";
import { Metrics } from "./pages/Metrics";
import { Receipt } from "./pages/Receipt";
import { Erp } from "./pages/Erp";
import { About } from "./pages/About";

const NAV = [
  { to: "/", label: "Overview", icon: <HomeIcon />, end: true },
  { to: "/inbox", label: "Inbox", icon: <InboxIcon /> },
  { to: "/red-team", label: "Red Team", icon: <Swords /> },
  { to: "/metrics", label: "Metrics", icon: <BarChart3 /> },
  { to: "/erp", label: "Ledger", icon: <Landmark /> },
  { to: "/about", label: "How it works", icon: <BookOpen /> },
];

type Theme = "system" | "light" | "dark";
function useTheme(): [Theme, () => void] {
  const [t, setT] = React.useState<Theme>(() => {
    try { return (localStorage.getItem("airlock-theme") as Theme) || "system"; } catch { return "system"; }
  });
  React.useEffect(() => {
    const el = document.documentElement;
    if (t === "system") el.removeAttribute("data-theme"); else el.setAttribute("data-theme", t);
    try { localStorage.setItem("airlock-theme", t); } catch { /* storage blocked */ }
  }, [t]);
  return [t, () => setT((x) => (x === "system" ? "light" : x === "light" ? "dark" : "system"))];
}

function Shell() {
  const loc = useLocation();
  const [health, setHealth] = React.useState<any>(null);
  const [menu, setMenu] = React.useState(false);
  const [theme, cycleTheme] = useTheme();

  React.useEffect(() => {
    api.session().catch(() => {});
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);
  React.useEffect(() => { setMenu(false); window.scrollTo({ top: 0 }); }, [loc.pathname]);

  const mode = health?.mode;
  const tier = health?.runner?.tier;
  const statusCls = !health ? "off" : !health.ok ? "warn" : mode === "mock" ? "warn" : "";
  const statusText = !health ? "Connecting…" : !health.ok ? "API unreachable" : mode === "mock" ? "Mock LLM · local" : `Live · ${tier?.includes("gvisor") ? "gVisor sandbox" : tier || "sandbox"}`;
  const section = "/" + (loc.pathname.split("/")[1] || "");
  const navKey = section === "/invoices" || section === "/receipts" ? "/inbox" : section;

  return (
    <>
      <header className="topbar">
        <div className="topbar-in">
          <Link to="/" className="brand" aria-label="Airlock home"><Logo />Airlock</Link>
          <nav className="nav" aria-label="Main">
            {NAV.map((n) => {
              const on = n.to === navKey;
              return (
                <NavLink key={n.to} to={n.to} end={n.end} className={on ? "active" : ""}>
                  {on && <motion.span layoutId="nav-pill" className="pill-bg" transition={{ duration: 0.3, ease }} />}
                  {n.icon}<span>{n.label}</span>
                </NavLink>
              );
            })}
          </nav>
          <div className="top-right">
            <span className={`status-dot ${statusCls}`} title={health?.runner?.runtime ? `runtime: ${health.runner.runtime}` : undefined}><i /><span className="lbl">{statusText}</span></span>
            <button className="icon-btn" onClick={cycleTheme} aria-label={`Theme: ${theme}`} title={`Theme: ${theme}`}>
              {theme === "light" ? <Sun /> : theme === "dark" ? <Moon /> : <Monitor />}
            </button>
            <button className="icon-btn menu-btn" onClick={() => setMenu((m) => !m)} aria-label="Menu" aria-expanded={menu}>{menu ? <X /> : <Menu />}</button>
          </div>
        </div>
      </header>
      <AnimatePresence>
        {menu && (
          <motion.nav className="mobile-nav" aria-label="Main" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2, ease }}>
            {NAV.map((n) => <NavLink key={n.to} to={n.to} end={n.end} className={n.to === navKey ? "active" : ""}>{n.icon}{n.label}</NavLink>)}
          </motion.nav>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait" initial={false}>
        <motion.main key={section === "/invoices" ? loc.pathname : section} className="page"
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, transition: { duration: 0.1 } }}
          transition={{ duration: 0.28, ease }}>
          <Routes location={loc}>
            <Route path="/" element={<Home />} />
            <Route path="/inbox" element={<Inbox />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route path="/red-team" element={<RedTeam />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/receipts/:id" element={<Receipt />} />
            <Route path="/erp" element={<Erp />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </motion.main>
      </AnimatePresence>

      <footer className="footer">
        <div className="footer-in">
          <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}><Logo size={18} /> Airlock by Team Beyonders</span>
          <span>Built on Vultr</span>
          <span className="grow" />
          <span>Fictional vendors and a mock ERP. No real payments.</span>
          <a href="https://github.com/Viranshul-P/vultr-agent-rush" target="_blank" rel="noreferrer">Source</a>
        </div>
      </footer>
    </>
  );
}

function NotFound() {
  return (
    <div className="empty" style={{ paddingTop: 80 }}>
      <h1>Page not found</h1>
      <p>That address doesn't match anything in Airlock.</p>
      <Link className="btn" to="/">Back to overview</Link>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <Shell />
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
);
