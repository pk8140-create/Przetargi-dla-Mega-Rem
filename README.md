# Skaner przetargów Mega-Rem

Codziennie pobiera ogłoszenia z BZP (e-Zamówienia) i TED, filtruje po słowach kluczowych i kodach CPV,
liczy odległość od Krakowa i generuje stronę `docs/index.html` (tabela z sortowaniem, filtrami i eksportem CSV).

## Uruchomienie (jednorazowo, ok. 5 minut)
1. Utwórz repozytorium na GitHubie (może być prywatne) i wgraj całą zawartość tego folderu.
2. Settings → Pages → Source: *Deploy from a branch*, branch `main`, folder `/docs`.
   (Strona na kontach darmowych wymaga repozytorium publicznego – dane to jawne ogłoszenia, ale zastanów się nad tym.)
3. Zakładka Actions → „Codzienny skan przetargów” → *Run workflow* (pierwszy przebieg pobiera 30 dni wstecz).
4. Po pierwszym przebiegu sprawdź w logu linię „BZP: OK / TED: OK”. Jeśli któreś źródło pokazuje BŁĄD albo 0 dopasowań,
   otwórz `data/debug_bzp.json` (surowe próbki z BZP) i popraw nazwy pól w funkcji `norm_bzp`.

## E-mail (opcjonalnie)
Dodaj w Settings → Secrets: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `MAIL_FROM`, `MAIL_TO`,
a w Variables: `PAGE_URL`. Mail wychodzi tylko, gdy są nowe pozycje.

## Strojenie
W `tenders.py`: listy `CORE`, `WEAK`, `CONTEXT`, `EXCL`, `CPV_PREFIXES`, `CITIES` oraz zmienna `RADIUS_KM`.

## Ograniczenia
- BZP nie podaje miejsca realizacji – odległość liczona jest od siedziby zamawiającego (lub środka województwa, oznaczone „~”).
- PGE (swpp2.gkpge.pl) i inne portale z CAPTCHA/logowaniem nie są skanowane; ich przetargi powyżej progów pojawiają się w BZP/TED.
- Test offline: `python tenders.py --offline` (dane syntetyczne z `tests/fixture.json`).
