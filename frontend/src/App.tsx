import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { CostPage } from "./pages/CostPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DemoPage } from "./pages/DemoPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReportPage } from "./pages/ReportPage";
import { ReviewPage } from "./pages/ReviewPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/demo" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/reviews" element={<ReviewPage />} />
        <Route path="/costs" element={<CostPage />} />
        <Route path="/dashboard/:runId" element={<DashboardPage />} />
        <Route path="/reports/:runId" element={<ReportPage />} />
      </Routes>
    </AppShell>
  );
}
