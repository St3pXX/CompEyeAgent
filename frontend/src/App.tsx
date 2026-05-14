import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DemoPage } from "./pages/DemoPage";
import { ReportPage } from "./pages/ReportPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/demo" replace />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/dashboard/:runId" element={<DashboardPage />} />
        <Route path="/reports/:runId" element={<ReportPage />} />
      </Routes>
    </AppShell>
  );
}
