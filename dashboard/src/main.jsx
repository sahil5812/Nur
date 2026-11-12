import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Cleanly unregister any stale service workers and purge browser cache
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (let reg of registrations) {
      reg.unregister();
    }
  });
}
if (typeof caches !== 'undefined') {
  caches.keys().then((keys) => {
    keys.forEach((key) => caches.delete(key));
  });
}

