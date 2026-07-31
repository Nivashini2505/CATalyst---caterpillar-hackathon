import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Shell } from '@/components/Shell';
import { Landing } from '@/pages/Landing';
import { Demand } from '@/pages/Demand';
import { Anomaly } from '@/pages/Anomaly';
import { Maintenance } from '@/pages/Maintenance';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/demand" element={<Demand />} />
          <Route path="/anomaly" element={<Anomaly />} />
          <Route path="/maintenance" element={<Maintenance />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  </React.StrictMode>,
);
