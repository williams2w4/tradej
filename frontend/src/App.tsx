import { BrowserRouter, Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import CalendarPage from "./pages/CalendarPage";
import Dashboard from "./pages/Dashboard";
import ImportPage from "./pages/ImportPage";
import Trades from "./pages/Trades";

const App = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="trades" element={<Trades />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="imports" element={<ImportPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
