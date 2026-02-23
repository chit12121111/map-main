import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout";
import DashboardPage from "./pages/dashboard";
import ViewsPage from "./pages/views";
import CustomerDetailsPage from "./pages/customerDetails";
import OrganizationsPage from "./pages/organizations";
import SettingsPage from "./pages/settings";
import LogsPage from "./pages/logs";

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/views" element={<ViewsPage />} />
        <Route path="/customers" element={<Navigate to="/views" replace />} />
        <Route path="/customer-details" element={<CustomerDetailsPage />} />
        <Route path="/customer-details/:placeId" element={<CustomerDetailsPage />} />
        <Route path="/organizations" element={<OrganizationsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}

