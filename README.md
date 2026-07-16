# AI Devs 4

> Moje rozwiązania 25 zadań z kursu [AI Devs 4](https://www.aidevs.pl/) — od interakcji z modelami po narzędzia i architekturę agentów.

![Status: Completed](https://img.shields.io/badge/status-completed-2ea44f)

## Overview

Repozytorium organizuje rozwiązania kursowe w pięciu sezonach (`S01`–`S05`), po pięć epizodów w każdym. Każde z 25 potwierdzonych rozwiązań jest notebookiem Jupyter umieszczonym w katalogu `solution` danego epizodu.

> [!IMPORTANT]
> Kurs jest prywatny. Repozytorium zawiera autorskie rozwiązania, natomiast wzorzec `**/notes/` w `.gitignore` wyklucza lokalne notatki i materiały kursowe.

## Project status

| Element | Informacja |
|---|---|
| Status | ✅ Completed |
| Zakres | 5 sezonów, 25 epizodów i 25 potwierdzonych notebooków |
| Ostatnia weryfikacja | Sprawdzono obecność wszystkich ścieżek rozwiązań; notebooków nie uruchamiano ponownie |

## Key features

- Spójna hierarchia pięciu sezonów i 25 epizodów.
- Notebooki obejmujące m.in. routing modeli i analizę kosztów, tool calling, pamięć, ewaluację oraz projektowanie agentów.
- Przykłady integracji z OpenAI i Anthropic.
- Implementacje aplikacyjne, np. serwer Flask w `S01/E03`.
- Eksperymenty z bezpiecznym wykonywaniem kodu w `S05/E01`.
- Master controller z rejestrem narzędzi, routingiem, pamięcią i poziomami autonomii w `S05/E05`.
- `.gitignore` wykluczający `.env`, lokalne notatki, środowisko `venv` i pliki cache Pythona.

## Results

Najważniejszym rezultatem jest kompletna, uporządkowana kolekcja 25 notebooków — po jednym dla każdej ścieżki rozwiązania wskazanej w repozytorium. Projekty mają różne cele, dlatego repozytorium nie ma jednej wspólnej metryki jakości. Oryginalne README nie dokumentuje też zbiorczej ewaluacji wszystkich rozwiązań.

## Tech stack

| Technologia | Potwierdzony plik | Zastosowanie |
|---|---|---|
| Python 3 / Jupyter Notebook | wszystkie ścieżki `solution/*.ipynb` | Implementacja i eksperymenty |
| OpenAI API | `S01/E01/solution/s01e01_agent.ipynb`, `S05/E05/solution/agent_master_controller.ipynb` | Wywołania modeli i routing |
| Anthropic API | `S01/E01/solution/s01e01_agent.ipynb` | Alternatywny dostawca modeli i prompt caching |
| tiktoken | `S01/E01/solution/s01e01_agent.ipynb` | Analiza tokenów i kosztów |
| python-dotenv | `S01/E01/solution/s01e01_agent.ipynb`, `S01/E03/solution/s01e03_proxy.ipynb` | Lokalne ładowanie sekretów |
| Flask i Requests | `S01/E03/solution/s01e03_proxy.ipynb` | Endpoint HTTP i komunikacja z API |
| E2B Code Interpreter i Bandit | `S05/E01/solution/agent_safe_execution.ipynb` | Sandbox i analiza bezpieczeństwa kodu |
| ChromaDB | `S05/E05/solution/agent_master_controller.ipynb` | Pamięć długoterminowa i epizodyczna |

## How it works

1. Wybierz sezon i epizod odpowiadający ćwiczeniu.
2. Otwórz notebook znajdujący się w katalogu `solution`.
3. Zainstaluj biblioteki importowane przez ten konkretny notebook.
4. Skonfiguruj wymagane zmienne środowiskowe w lokalnym pliku `.env`.
5. Uruchom komórki kolejno i przeanalizuj wynik danego eksperymentu.

Poszczególne notebooki są samodzielnymi rozwiązaniami; repozytorium nie zawiera wspólnego runnera ani głównego manifestu zależności.

## Repository structure

Poniższa hierarchia pokazuje wyłącznie ścieżki potwierdzone w repozytorium:

```text
.
├── .gitignore
├── README.md
├── S01/
│   └── E01/ ... E05/
│       └── solution/<notebook>.ipynb
├── S02/
│   └── E01/ ... E05/
│       └── solution/<notebook>.ipynb
├── S03/
│   └── E01/ ... E05/
│       └── solution/<notebook>.ipynb
├── S04/
│   └── E01/ ... E05/
│       └── solution/<notebook>.ipynb
└── S05/
    └── E01/ ... E05/
        └── solution/<notebook>.ipynb
```

### Verified solution index

| Sezon | Notebooki |
|---|---|
| S01 | [E01](S01/E01/solution/s01e01_agent.ipynb) · [E02](S01/E02/solution/s01e02_findhim.ipynb) · [E03](S01/E03/solution/s01e03_proxy.ipynb) · [E04](S01/E04/solution/s01e04_sendit.ipynb) · [E05](S01/E05/solution/s01e05_railway.ipynb) |
| S02 | [E01](S02/E01/solution/s02e01_categorize.ipynb) · [E02](S02/E02/solution/s02e02_electricity.ipynb) · [E03](S02/E03/solution/s02e03_failure.ipynb) · [E04](S02/E04/solution/s02e04_mailbox.ipynb) · [E05](S02/E05/solution/s02e05_drone.ipynb) |
| S03 | [E01](S03/E01/solution/s03e01_evaluation.ipynb) · [E02](S03/E02/solution/s03e02_firmware.ipynb) · [E03](S03/E03/solution/s03e03_reactor.ipynb) · [E04](S03/E04/solution/s03e04_negotiations.ipynb) · [E05](S03/E05/solution/s03e05_savethem.ipynb) |
| S04 | [E01](S04/E01/solution/s04e01_okoeditor.ipynb) · [E02](S04/E02/solution/s04e02_windpower.ipynb) · [E03](S04/E03/solution/s04e03_domatowo.ipynb) · [E04](S04/E04/solution/s04e04_filesystem.ipynb) · [E05](S04/E05/solution/s04e05_foodwarehouse.ipynb) |
| S05 | [E01](S05/E01/solution/agent_safe_execution.ipynb) · [E02](S05/E02/solution/agent_tool_integration.ipynb) · [E03](S05/E03/solution/agent_functional_development.ipynb) · [E04](S05/E04/solution/agent_production_ready.ipynb) · [E05](S05/E05/solution/agent_master_controller.ipynb) |

## Getting started

```bash
git clone https://github.com/DominikDawiec/ai-devs-4.git
cd ai-devs-4

python -m venv venv
source venv/bin/activate
```

Repozytorium nie zawiera `requirements.txt` ani `pyproject.toml`, dlatego instaluj zależności właściwe dla wybranego notebooka. Przykładowo `S01/E01` importuje:

```bash
pip install openai anthropic python-dotenv tiktoken
```

Utwórz lokalny plik `.env` — jest wykluczony przez `.gitignore` — i dodaj tylko zmienne potrzebne w wybranym ćwiczeniu. Potwierdzone przykłady to:

```dotenv
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AI_DEVS_API_KEY=...
```

Repozytorium nie zawiera obecnie `.env.example`; nie dodawaj prawdziwego `.env` do Git.

## Usage

Otwórz wybrany notebook w Jupyter lub VS Code i przeczytaj jego pierwszą komórkę przed instalowaniem pakietów lub uruchamianiem kodu. Część rozwiązań wywołuje zewnętrzne modele, API kursowe albo lokalny serwer, a niektóre komórki mogą wykonywać działania lub generować koszt.

Uruchamiaj notebooki pojedynczo, z minimalnym zakresem kluczy i uprawnień. Nie publikuj prywatnych danych kursowych, odpowiedzi API ani sekretów.

## Data and methodology

Metodyka zależy od epizodu. Potwierdzone przykłady obejmują routing zadań pomiędzy modelami i kalkulację kosztów (`S01/E01`), serwer proxy z narzędziami (`S01/E03`), warstwy bezpiecznego wykonywania kodu (`S05/E01`) oraz kontroler agentowy z pamięcią i poziomami autonomii (`S05/E05`).

Materiały źródłowe kursu nie są częścią repozytorium; `.gitignore` wyklucza katalogi `notes`. Wyniki notebooków należy więc interpretować jako rozwiązania edukacyjne zależne od prywatnego kontekstu i zewnętrznych usług.

## Limitations

- Brak wspólnego `requirements.txt` lub `pyproject.toml` utrudnia powtarzalne uruchomienie całej kolekcji.
- Brak `.env.example`; wymagane zmienne trzeba odczytać z poszczególnych notebooków.
- Rozwiązania mogą wymagać prywatnych API i danych kursowych, których repozytorium celowo nie zawiera.
- Notebooki korzystają z usług zewnętrznych, których modele, ceny i interfejsy mogą się zmieniać.
- Komórki instalacyjne oraz kod wykonujący działania wymagają indywidualnego przeglądu przed uruchomieniem.
- Jest to materiał edukacyjny, a nie jeden przetestowany system produkcyjny.

## Contact

Autor: [Dominik Dawiec](https://www.linkedin.com/in/dominikdawiec/).
