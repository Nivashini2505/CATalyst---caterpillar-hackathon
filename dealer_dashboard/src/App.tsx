import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { MissionControlPage } from '@/pages/MissionControlPage';
import { FleetPage } from '@/pages/FleetPage';
import { EquipmentDetailsPage } from '@/pages/EquipmentDetailsPage';
import { LiveOperationsPage } from '@/pages/LiveOperationsPage';
import { SitesPage } from '@/pages/SitesPage';
import { WorkforcePage } from '@/pages/WorkforcePage';
import { DecisionCenterPage } from '@/pages/DecisionCenterPage';
import { ForecastPage } from '@/pages/ForecastPage';
import { CopilotPage } from '@/pages/CopilotPage';
import { SettingsPage } from '@/pages/SettingsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<MissionControlPage />} />
          <Route path="/fleet" element={<FleetPage />} />
          <Route path="/equipment/:id" element={<EquipmentDetailsPage />} />
          <Route path="/operations" element={<LiveOperationsPage />} />
          <Route path="/sites" element={<SitesPage />} />
          <Route path="/workforce" element={<WorkforcePage />} />
          <Route path="/decisions" element={<DecisionCenterPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/copilot" element={<CopilotPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
