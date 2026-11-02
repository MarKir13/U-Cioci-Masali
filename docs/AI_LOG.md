# Dziennik AI

Zasady:
- Wpis dodaje osoba, która korzystała z narzędzia, w tym samym PR co kod.
- PR z istotnymi fragmentami wygenerowanymi przez AI dostaje etykietę `ai-assisted`, a w opisie wyjaśnia, jak zweryfikowano poprawność.
- Nie wklejamy do narzędzi AI haseł, kluczy API ani danych dostępowych do klastra.

| Data i autor | Narzędzie i model | Zadanie | Co otrzymano | Co było błędne | Weryfikacja |
|---|---|---|---|---|---|
| 28.10.2026<br>Marcel Kiraga | Claude Code (VS Code), Claude Opus 5.5 | Issue #1, PR #2: struktura repozytorium, obraz sklepu, stack Docker Compose, dokumentacja | `.gitignore`, `shop/Dockerfile` z `php.ini`, motyw potomny `ciocia`, `deploy/compose.yaml` z `.env.example`, skrypt `sync-code.sh`, szablony `docs/`, README | 1) `compose.yaml` w katalogu głównym zamiast w `deploy/`.<br>2) Zbędne zalecenie wyłączania `PS_INSTALL_AUTO` po instalacji.<br>3) Pominięto, że wolumen przesłania pliki z nowego obrazu (motyw by się nie aktualizował); poprawione skryptem `sync-code.sh`; | Przegląd każdego commita; instalacja serwisów od zera (~3,5 min), weryfikacja poprawności bezpośrednio na stronach sklepu oraz panelu admina; test aktualizacji motywu po przebudowie; ustawienia PHP potwierdzone w kontenerze. |
| 02.11.2026<br>Marcel Kiraga | Claude Code (VS Code), Claude Opus 5.5 | Issue #14: plan CI/CD, instrukcje dla agentów AI, pipeline z ruff i testami scrapera | `docs/ci-cd-plan.md` z planem i propozycjami issues, `AGENTS.md` z wymaganiami i opisem sklepu źródłowego, `CLAUDE.md`, `ruff.toml`, `.github/workflows/ci.yml`, sekcja CI w README | 1) Szkic `ruff.toml` bez `src = ["scraper"]` dawał fałszywy błąd `I001` przy uruchomieniu z katalogu głównego.<br>2) Wyniki ruff dla PR #4 w planie zdezaktualizowały się po nowych commitach i zostały policzone ponownie. | gitleaks na całej historii wykrył tokeny w fixture'ach PR #4 (do usunięcia przed scaleniem). `ruff.toml` sprawdzony na kopii PR #4: ten sam wynik z katalogu głównego i ze `scraper/`, po poprawkach ruff bez błędów i 78 testów przechodzi (Python 3.13). `ci.yml` sprawdzony narzędziem actionlint. Działanie na GitHub Actions i Pythonie 3.12 potwierdzi przebieg w tym PR. |

## Refleksja zespołu

_Uzupełniana na koniec etapu: gdzie AI realnie przyspieszyło pracę, gdzie wprowadziło w błąd i czego zespół musiał nauczyć się sam._
