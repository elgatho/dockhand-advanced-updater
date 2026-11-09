# Dockhand Advanced Updater

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Integracja Home Assistant dodająca **zaplanowane autoaktualizacje z uwzględnieniem obecności** dla kontenerów zarządzanych przez [Dockhand](https://dockhand.pro). 🇬🇧 [English version](README.md)

## Funkcje

- Lista wszystkich kontenerów ze wszystkich (lub wybranych) środowisk Dockhand.
- **Wykluczanie** kontenerów z autoaktualizacji; wykluczone dostają przycisk ręcznej aktualizacji.
- Autoaktualizacja o wybranej **godzinie** w wybrane **dni tygodnia**: aktualizowane są wszystkie niewykluczone kontenery, dla których Dockhand znalazł nowy obraz.
- Opcja **„tylko gdy ktoś jest w domu"** z wyborem encji `person`. Jeśli o zaplanowanej godzinie nikogo nie ma, aktualizacja jest odroczona i ruszy po powrocie wybranej osoby (tego samego dnia).
- Szanuje *minimalny wiek wydania* z Dockhand (kontenery w okresie oczekiwania są pomijane).
- Encje: sensor binarny „dostępna aktualizacja" dla każdego kontenera, sensory *Oczekujące aktualizacje*, *Następna autoaktualizacja*, *Ostatnie uruchomienie*, przełącznik *Autoaktualizacja*, przyciski *Sprawdź aktualizacje* i *Wymuś autoaktualizację* (uruchamia autoaktualizację od razu, tylko dla kontenerów niewykluczonych; wykluczone nigdy nie są ruszane).
- Zdarzenie `dockhand_advanced_updater_run_finished` (`reason`, `updated`, `failed`, `finished`) – do powiadomień.
- Pełna konfiguracja z UI (config flow, opcje, ponowne uwierzytelnienie) po polsku i angielsku.
- Naciśnięcie przycisku wyświetla powiadomienie (start / koniec z wynikiem); kolejne naciśnięcia w trakcie aktualizacji są odrzucane.

## Przykładowy dashboard

Gotowa karta (statusy, oczekujące aktualizacje, przyciski ręcznej aktualizacji) jest w [`examples/dashboard.yaml`](examples/dashboard.yaml). Wymaga karty [auto-entities](https://github.com/thomasloven/lovelace-auto-entities); obie listy wypełniają się same, wystarczy dopasować pięć identyfikatorów encji statusu na górze.

## Instalacja

### HACS (repozytorium niestandardowe)
1. HACS → ⋮ → *Niestandardowe repozytoria* → dodaj to repozytorium, kategoria **Integration**.
2. Zainstaluj **Dockhand Advanced Updater** i zrestartuj Home Assistant.

### Ręcznie
Skopiuj `custom_components/dockhand_advanced_updater` do `config/custom_components/` i zrestartuj HA.

## Konfiguracja

1. *Ustawienia → Urządzenia i usługi → Dodaj integrację → Dockhand Advanced Updater*.
2. Podaj adres Dockhand i **token API** (profil Dockhand → tokeny API; token musi mieć uprawnienia do listowania i odtwarzania kontenerów). Token zostaw pusty tylko, gdy uwierzytelnianie w Dockhand jest wyłączone.
3. Kliknij **Konfiguruj** przy integracji i ustaw:
   - środowiska, godzinę, dni, „tylko gdy w domu" + osoby, interwał odświeżania,
   - następnie listę kontenerów **wykluczonych** z autoaktualizacji.

Zmiana opcji przeładowuje integrację. Przyciski powstają tylko dla kontenerów wykluczonych.

## Jak to działa

Aktualizacje używają endpointu batch-update Dockhand: pobiera nowy obraz i odtwarza kontener z zachowaniem konfiguracji. Kontenery są identyfikowane jako `id środowiska : nazwa`, bo ID Dockera zmienia się po każdej aktualizacji.

## Uwagi

- Aktualizację wykonuje Dockhand; HA ją tylko wyzwala. Kontener z samym Home Assistant aktualizuj ręcznie.
- Wymaga Home Assistant 2024.11 lub nowszego.

## Licencja
MIT
