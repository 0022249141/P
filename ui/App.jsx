import React, { useEffect, useMemo, useState } from 'react';
import Dashboard from './components/Dashboard';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import rtlPlugin from 'stylis-plugin-rtl';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';

const cacheRtl = createCache({ key: 'muirtl', stylisPlugins: [rtlPlugin] });
const WS_URL = import.meta?.env?.VITE_WS_URL || 'ws://localhost:8000/ws';

function App() {
  const [data, setData] = useState({ signals: [], narratives: [], market_state: 'unresolved' });
  const theme = useMemo(() => createTheme({ direction: 'rtl' }), []);

  useEffect(() => {
    let ws;
    let reconnect;
    const connect = () => {
      ws = new WebSocket(WS_URL);
      ws.onmessage = (event) => {
        try { setData(JSON.parse(event.data)); } catch (e) { console.error('Invalid WS payload', e); }
      };
      ws.onclose = () => { reconnect = setTimeout(connect, 2000); };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => { if (reconnect) clearTimeout(reconnect); if (ws) ws.close(); };
  }, []);

  return (
    <CacheProvider value={cacheRtl}>
      <ThemeProvider theme={theme}>
        <Dashboard data={data} />
      </ThemeProvider>
    </CacheProvider>
  );
}
export default App;
