# AI Devs 4

Moje rozwiązania zadań z kursu **[AI Devs 4](https://www.aidevs.pl/)** — praktycznego kursu o budowaniu aplikacji i agentów opartych na modelach językowych.

> **Uwaga:** Kurs jest prywatny, dlatego to repozytorium zawiera wyłącznie moje propozycje rozwiązań zadań. Materiały z lekcji (notatki, transkrypcje, pliki kursowe) są przechowywane lokalnie i wykluczone z repozytorium przez `.gitignore`.

## Struktura

Każdy sezon (`S01`–`S05`) zawiera pięć epizodów (`E01`–`E05`). W każdym epizodzie:

```
S01/
├── E01/
│   ├── notes/      ← materiały z lekcji (lokalne, niewidoczne w repo)
│   └── solution/   ← moje rozwiązanie zadania
├── E02/
│   ├── notes/
│   └── solution/
├── ...
└── E05/
    ├── notes/
    └── solution/
S02/ ... S05/  (ta sama struktura)
```

## Tech stack

| Technologia | Wersja | Zastosowanie |
|-------------|--------|--------------|
| Python | 3.12 | język główny |
| Jupyter Notebook | — | większość rozwiązań |
| `anthropic` | 0.86.0 | Anthropic / Claude API |
| `openai` | 2.29.0 | OpenAI API |
| `python-dotenv` | 1.2.2 | zarządzanie sekretami przez `.env` |
| `requests` | 2.32.5 | HTTP do zewnętrznych API kursu |

## Uruchomienie

```bash
git clone https://github.com/DominikDawiec/ai-devs-4.git
cd ai-devs-4

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install anthropic openai python-dotenv requests tiktoken
```

Skopiuj `.env.example` (lub utwórz `.env`) i uzupełnij klucze API:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
```

## Sezony i tematy

### S01 — Podstawy pracy z modelem

| Epizod | Temat | Rozwiązanie |
|--------|-------|-------------|
| E01 | Programowanie interakcji z modelem językowym | [agent.py](S01/E01/solution/agent.py) |
| E02 | Techniki łączenia modelu z narzędziami | — |
| E03 | Projektowanie API dla efektywnej pracy z modelem | — |
| E04 | Wsparcie multimodalności oraz załączników | — |
| E05 | Zarządzanie jawnymi oraz niejawnymi limitami modeli | — |

### S02 — Zarządzanie kontekstem

| Epizod | Temat | Rozwiązanie |
|--------|-------|-------------|
| E01 | Zarządzanie kontekstem w konwersacji | — |
| E02 | Zewnętrzny kontekst narzędzi i dokumentów | — |
| E03 | Dokumenty oraz pamięć długoterminowa jako narzędzia | — |
| E04 | Organizowanie kontekstu dla wielu wątków | [agent.py](S02/E04/solution/agent.py) |
| E05 | Projektowanie agentów | [agent.py](S02/E05/solution/agent.py) |

### S03 — Ewaluacja i narzędzia

| Epizod | Temat | Rozwiązanie |
|--------|-------|-------------|
| E01 | Obserwowanie i ewaluacja | — |
| E02 | Ograniczenia modeli na etapie założeń projektu | — |
| E03 | Kontekstowy feedback wspierający skuteczność agentów | [s03e03_reactor.ipynb](S03/E03/solution/s03e03_reactor.ipynb) |
| E04 | Budowanie narzędzi na podstawie danych testowych | [s03e04_negotiations.ipynb](S03/E04/solution/s03e04_negotiations.ipynb) |
| E05 | Niedeterministyczna natura modeli jako przewaga | [s03e05_savethem.ipynb](S03/E05/solution/s03e05_savethem.ipynb) |

### S04 — Wdrożenia i współpraca z AI

| Epizod | Temat | Rozwiązanie |
|--------|-------|-------------|
| E01 | Wdrożenia rozwiązań AI | [s04e01_okoeditor.ipynb](S04/E01/solution/s04e01_okoeditor.ipynb) |
| E02 | Aktywna współpraca z AI | — |
| E03 | Kontekstowa współpraca z AI | [s04e03_domatowo.ipynb](S04/E03/solution/s04e03_domatowo.ipynb) |
| E04 | Projektowanie własnej bazy wiedzy dla AI | [s04e04_filesystem.ipynb](S04/E04/solution/s04e04_filesystem.ipynb) |
| E05 | Projektowanie rozwiązań wewnątrzfirmowych | [s04e05_foodwarehouse.ipynb](S04/E05/solution/s04e05_foodwarehouse.ipynb) |

### S05 — Agenty produkcyjne

| Epizod | Temat | Rozwiązanie |
|--------|-------|-------------|
| E01 | Architektura | [agent_safe_execution.ipynb](S05/E01/solution/agent_safe_execution.ipynb) |
| E02 | Zestaw narzędzi | [agent_tool_integration.ipynb](S05/E02/solution/agent_tool_integration.ipynb) |
| E03 | Rozwój funkcjonalności | [agent_functional_development.ipynb](S05/E03/solution/agent_functional_development.ipynb) |
| E04 | Produkcja | [agent_production_ready.ipynb](S05/E04/solution/agent_production_ready.ipynb) |
| E05 | Secret | [agent_master_controller.ipynb](S05/E05/solution/agent_master_controller.ipynb) |
