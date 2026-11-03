import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import "./styles.css";
import { api } from "./api";
import { Inbox } from "./pages/Inbox";
import { InvoiceDetail } from "./pages/InvoiceDetail";
import { RedTeam } from "./pages/RedTeam";
import { Metrics } from "./pages/Metrics";
import { Receipt } from "./pages/Receipt";
import { Erp } from "./pages/Erp";
import { About } from "./pages/About";

function Shell() {
  const [mode, setMode] = React.useState<string>("");
  React.useEffect(() => {
    api.session().catch(() => {});
    api.health().then((h) => setMode(h.mode)).catch(() => {});
  }, []);
  return (
    <div className="app">
      <header className="top">
        <span className="brand">Air<span className="dot">·</span>lock</span>
        <nav className="main">
          <NavLink to="/" end>Inbox</NavLink>
          <NavLink to="/red-team">Red Team</NavLink>
          <NavLink to="/metrics">Metrics</NavLink>
          <NavLink to="/erp">ERP</NavLink>
          <NavLink to="/about">How it works</NavLink>
        </nav>
        <span className="spacer" />
        {mode === "mock" && <span className="pill mock">MOCK LLM</span>}
        <span className="pill">Team Beyonders · Vultr</span>
      </header>
      <Routes>
        <Route path="/" element={<Inbox />} />
        <Route path="/invoices/:id" element={<InvoiceDetail />} />
        <Route path="/red-team" element={<RedTeam />} />
        <Route path="/metrics" element={<Metrics />} />
        <Route path="/receipts/:id" element={<Receipt />} />
        <Route path="/erp" element={<Erp />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  </React.StrictMode>
);
