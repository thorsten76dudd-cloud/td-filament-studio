# GitHub-Nutzung — Vergleichsbasis

**Erstellt:** 2026-05-21 (nach Release v1.5.67-stable)  
**Repo:** https://github.com/thorsten76dudd-cloud/td-filament-studio

> GitHub-Traffic-API zeigt nur die **letzten 14 Tage**. Release-Downloads zählen pro Asset; ältere `-stable`-Releases wurden gelöscht (kein historischer Download-Stand mehr auf GitHub).

## Repo (Stand 2026-05-21)

| Metrik | Wert |
|--------|------|
| Erstellt | 2026-05-20 |
| Stars | 0 |
| Forks | 0 |
| Watchers | 0 |
| Offene Issues | 0 |

## Traffic (letzte 14 Tage, API)

| | Gesamt | Eindeutig |
|--|--------|-----------|
| **Seitenaufrufe** (Views) | 54 | 1 |
| **Git-Clones** | 11 | 11 |

## Releases

| Tag | Veröffentlicht | Setup-Downloads |
|-----|----------------|-----------------|
| v1.5.67-stable | 2026-05-21 16:39 UTC | 0 |

*Nur noch ein Release auf GitHub (Latest). Vorherige Tags/Releases entfernt — Download-Zahlen der alten Versionen sind nicht mehr abrufbar.*

## Nächster Vergleich

Gleiche Werte erneut abfragen:

```powershell
gh repo view thorsten76dudd-cloud/td-filament-studio --json stargazerCount,forkCount
gh api repos/thorsten76dudd-cloud/td-filament-studio/traffic/views --jq '"views: " + (.count|tostring) + " total, " + (.uniques|tostring) + " unique"'
gh api repos/thorsten76dudd-cloud/td-filament-studio/traffic/clones --jq '"clones: " + (.count|tostring) + " total, " + (.uniques|tostring) + " unique"'
gh api "repos/thorsten76dudd-cloud/td-filament-studio/releases/latest" --jq '"downloads: " + ([.assets[].download_count]|add|tostring)'
```

Neue Zeile unten anfügen mit Datum + Zahlen.

---

### Vergleichs-Log

| Datum | Views (14d) | Clones (14d) | Stars | Latest-Downloads |
|-------|-------------|--------------|-------|------------------|
| 2026-05-21 | 54 / 1 unique | 11 / 11 unique | 0 | 0 |
