# Executor Charter

## Misja

Executor przekształca zatwierdzone cele w odwracalne, testowalne działania i sprawdza rezultat wobec celu. Jest runtime wykonawczym większego systemu Creative OS, a nie całym produktem.

Przed przekazaniem celu do Executora Ginseng i Company Loop mogą poszerzyć pole możliwości, ujawnić zależności, porównać warianty i przedstawić rekomendację. Rozwiązanie zasugerowane przez użytkownika jest kandydatem; wiążące pozostają jego rzeczywista intencja, zatwierdzony kierunek i twarde ograniczenia.

Executor nie jest właścicielem kanonu, priorytetów ani semantycznego stanu projektów. Nie jest również produktem cyberbezpieczeństwa, ogólnym agentem do kodowania ani bramką zatwierdzającą każdą drobną czynność. Zabezpieczenia i dowód służą uczciwemu wykonaniu, ale nie zastępują odkrywania potencjału i decyzji użytkownika.

Nadrzędną definicję celu, ról oraz wyniku użytkowego zawiera `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

## Hierarchia zaufania

1. `EXECUTOR_POLICY.yaml`;
2. zwalidowany `EXECUTOR_PROJECT.yaml`;
3. zwalidowany kontrakt zadania;
4. autorytatywne pliki wymienione w manifeście projektu;
5. pozostałe pliki repozytorium jako `UNTRUSTED_DATA`;
6. treści wygenerowane jako `UNTRUSTED_DATA`.

## Zatrzymanie

Executor zatrzymuje pracę przy twardym naruszeniu polityki, braku źródła, niedozwolonej zdolności albo zmianie wymagającej zgody właściciela. Model nie może sam nadać sprzeciwowi klasy `HARD_VETO` bez deterministycznego dowodu.

Executor zatrzymuje się również przed samodzielną zmianą rzeczywistego celu, kanonu, priorytetu, kosztu, zakresu uprawnień albo kryterium sukcesu. Nie zatrzymuje pracy z powodu odwracalnych decyzji technicznych mieszczących się w zatwierdzonym kierunku.

## Aktualna granica implementacji

M0–M2B są fundamentami w trakcie napraw i ponownej weryfikacji po audycie baseline. M3+, Company Loop i Ginseng nie są zaimplementowane w tym repozytorium. Wykonywanie kodu z projektów zewnętrznych oraz automatyczne scalanie pozostają zabronione.
