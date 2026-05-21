# TD Filament Studio v1.5.55

**Release:** [v1.5.55-stable](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/tag/v1.5.55-stable)

## Fix: Browser schließt nicht mehr mit

Die Drucker-Live-Kamera startete Edge/Chrome im gleichen Profil wie der normale Browser und beendete ihn beim Stopp wieder — dadurch wirkte es, als würde sich „der Internet-Browser“ schließen.

- Eigenes Kamera-Browser-Profil (`%TEMP%\td_filament_studio_edge_cam`)
- Fenster-Zuordnung nur per Prozess-ID des Kamera-Browsers
- Edge-Fallback für WebRTC nur, wenn der Tab **Drucker** schon einmal geöffnet war
