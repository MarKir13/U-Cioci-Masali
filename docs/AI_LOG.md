# Dziennik AI

Zasady:
- Wpis dodaje osoba, która korzystała z narzędzia, w tym samym PR co kod.
- PR z istotnymi fragmentami wygenerowanymi przez AI dostaje etykietę `ai-assisted`, a w opisie wyjaśnia, jak zweryfikowano poprawność.
- Nie wklejamy do narzędzi AI haseł, kluczy API ani danych dostępowych do klastra.

| Data i autor | Narzędzie i model | Zadanie | Co otrzymano | Co było błędne | Weryfikacja |
|---|---|---|---|---|---|
| 28.10.2026<br>Marcel Kiraga | Claude Code (VS Code), Claude Opus 5.5 | Issue #1, PR #2: struktura repozytorium, obraz sklepu, stack Docker Compose, dokumentacja | `.gitignore`, `shop/Dockerfile` z `php.ini`, motyw potomny `ciocia`, `deploy/compose.yaml` z `.env.example`, skrypt `sync-code.sh`, szablony `docs/`, README | 1) `compose.yaml` w katalogu głównym zamiast w `deploy/`.<br>2) Zbędne zalecenie wyłączania `PS_INSTALL_AUTO` po instalacji.<br>3) Pominięto, że wolumen przesłania pliki z nowego obrazu (motyw by się nie aktualizował); poprawione skryptem `sync-code.sh`; | Przegląd każdego commita; instalacja serwisów od zera (~3,5 min), weryfikacja poprawności bezpośrednio na stronach sklepu oraz panelu admina; test aktualizacji motywu po przebudowie; ustawienia PHP potwierdzone w kontenerze. |

## Refleksja zespołu

_Uzupełniana na koniec etapu: gdzie AI realnie przyspieszyło pracę, gdzie wprowadziło w błąd i czego zespół musiał nauczyć się sam._
