"""
S01E01: Model Router & Analizator Kosztów
==========================================

Lekcja uczy: kontrola kosztów, zarządzanie tokenami, routing modeli.
Ten skrypt demonstruje te koncepty w praktyce.

Czego się nauczysz (Python 3.12):
  - dataclasses        → lekkie klasy do danych, bez boilerplate'u
  -Enum               → bezpieczne stałe zamiast "magic strings"
  - type aliases (X|Y) → nowa składnia unii typów z 3.10+
  - tiktoken           → liczenie tokenów OpenAI przed wysłaniem
  - f-stringi z formatowaniem → np. f"{cost:.6f}" do wyświetlania groszy

Czego się nauczysz (GenAI):
  - Dlaczego tokeny wyjściowe są 3-5x droższe niż wejściowe
  - Jak routować zapytania: proste → tani model, złożone → drogi
  - Jak działa prompt caching w Anthropic (do 90% oszczędności)
  - Dlaczego polski tekst kosztuje ~50-70% więcej niż angielski (tokenizacja)
  - Jak policzyć koszt PRZED wysłaniem zapytania

Uruchomienie:
  cd AI_Devs_4
  source venv/bin/activate
  python S01E01/agent.py
"""

import os
import time
from enum import Enum
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI
from anthropic import Anthropic
import tiktoken

# ── ŁADOWANIE KLUCZY ─────────────────────────────────────────────────────────
# dotenv szuka pliku .env w katalogu nadrzędnym (wspólny dla wszystkich projektów)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# ── KONFIGURACJA MODELI ──────────────────────────────────────────────────────
# Lekcja S01E01: "Który model jest wystarczający do zadania?"
#
# Kluczowa zasada: nie każde zadanie wymaga najdroższego modelu.
# Przykład z lekcji: przetwarzanie faktur zmniejszone z $45k/mies
# do $0.60/mies przez dobór modelu + caching + batch.


class ModelTier(Enum):
    """Trzy poziomy modeli - od najtańszego do najdroższego.

    Enum zamiast stringów → IDE podpowie opcje, literówka = błąd w runtime.
    Porównaj z pisaniem tier = "chepa" - nikt Ci tego nie złapie.
    """
    CHEAP = "cheap"           # klasyfikacja, ekstrakcja, tak/nie
    MEDIUM = "medium"         # tłumaczenie, podsumowanie, proste pytania
    EXPENSIVE = "expensive"   # analiza, rozumowanie, porównywanie


@dataclass
class ModelConfig:
    """Konfiguracja jednego modelu - nazwa, ceny, provider.

    dataclass generuje __init__, __repr__, __eq__ automatycznie.
    Zamiast pisać:
        def __init__(self, name, provider, input_price, ...):
            self.name = name
            self.provider = provider
            ...
    Wystarczy zdefiniować pola.
    """
    name: str
    provider: str                       # "openai" | "anthropic"
    input_price_per_1m: float           # USD za 1M tokenów wejściowych
    output_price_per_1m: float          # USD za 1M tokenów wyjściowych
    cached_input_price_per_1m: float = 0.0   # Anthropic: cena za cached tokeny


# Cennik modeli (stan na 2025)
# Źródło: https://openai.com/pricing, https://docs.anthropic.com/en/docs/about-claude/models
#
# UWAGA na proporcje:
#   gpt-4o-mini:  wyjście 4x droższe niż wejście
#   gpt-4o:       wyjście 4x droższe niż wejście
#   claude-haiku: wyjście 5x droższe niż wejście
#
# Wniosek: zawsze proś model o ZWIĘZŁE odpowiedzi - to realna oszczędność.

MODELS: dict[ModelTier, ModelConfig] = {
    ModelTier.CHEAP: ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        input_price_per_1m=0.15,
        output_price_per_1m=0.60,
    ),
    ModelTier.MEDIUM: ModelConfig(
        name="claude-haiku-4-5-20251001",
        provider="anthropic",
        input_price_per_1m=1.00,
        output_price_per_1m=5.00,
        cached_input_price_per_1m=0.10,   # 10x taniej z cache!
    ),
    ModelTier.EXPENSIVE: ModelConfig(
        name="gpt-4o",
        provider="openai",
        input_price_per_1m=2.50,
        output_price_per_1m=10.00,
    ),
}


# ── WYNIK ZADANIA ────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    """Wynik pojedynczego wywołania LLM - odpowiedź + metryki kosztowe.

    Zbieramy te dane, żeby na końcu pokazać podsumowanie:
    ile kosztowało z routingiem vs ile kosztowałoby na samym GPT-4o.
    """
    task_name: str
    model_used: str
    tier: ModelTier
    response: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0


# ── FUNKCJE POMOCNICZE ───────────────────────────────────────────────────────


def count_tokens_openai(text: str) -> int:
    """Zlicz tokeny w tekście używając tokenizera OpenAI (tiktoken).

    Dlaczego to ważne:
    - Możesz oszacować koszt PRZED wysłaniem zapytania
    - Możesz sprawdzić czy zmieścisz się w limicie kontekstu
    - tiktoken jest deterministyczny - zawsze ten sam wynik dla tego samego tekstu
    """
    encoder = tiktoken.encoding_for_model("gpt-4o")
    return len(encoder.encode(text))


def calculate_cost(
    config: ModelConfig,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Oblicz koszt wywołania w USD.

    Formuła:
      koszt = (normalne_input * cena_input + cached * cena_cached + output * cena_output) / 1_000_000

    Ceny podawane są za 1 MILION tokenów, dlatego dzielimy przez 1_000_000.
    Typowe wywołanie zużywa 100-2000 tokenów, więc koszty są w ułamkach centa.
    """
    regular_input = input_tokens - cached_tokens
    return (
        regular_input * config.input_price_per_1m
        + cached_tokens * config.cached_input_price_per_1m
        + output_tokens * config.output_price_per_1m
    ) / 1_000_000


def classify_complexity(task: str) -> ModelTier:
    """Prosty router oparty na słowach kluczowych.

    W produkcji mógłbyś użyć:
    - regex + heurystyki (jak tutaj, ale bardziej rozbudowane)
    - taniego LLM do klasyfikacji złożoności (meta-routing)
    - embeddingi + klasyfikator (jeśli masz dane treningowe)

    Lekcja S01E01: "Trzeba zadać sobie pytanie: czy do tego zadania
    w ogóle potrzebuję AI, a jeśli tak - którego modelu?"
    """
    task_lower = task.lower()

    # Proste: krótkie, binarne, ekstrakcyjne
    simple_keywords = ["sklasyfikuj", "tak lub nie", "true/false", "wyodrębnij", "ile"]
    if any(kw in task_lower for kw in simple_keywords):
        return ModelTier.CHEAP

    # Złożone: wymagają rozumowania, analizy, porównań
    complex_keywords = ["przeanalizuj", "porównaj", "oceń", "wyjaśnij dlaczego", "strategia"]
    if any(kw in task_lower for kw in complex_keywords):
        return ModelTier.EXPENSIVE

    # Domyślnie: średni model
    return ModelTier.MEDIUM


# ── WYWOŁANIA API ────────────────────────────────────────────────────────────
# Dwa providery, dwa SDK, ale ta sama logika:
#   wyślij system prompt + user message → odbierz odpowiedź + usage stats


def call_openai(model: str, system: str, user_msg: str) -> tuple[str, int, int]:
    """Wywołanie OpenAI API.

    Zwraca krotkę (tuple) - lekki sposób na zwrócenie kilku wartości.
    tuple[str, int, int] to: (odpowiedź, tokeny_wejściowe, tokeny_wyjściowe)
    """
    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=500,
    )
    usage = response.usage
    return (
        response.choices[0].message.content,
        usage.prompt_tokens,
        usage.completion_tokens,
    )


def call_anthropic(
    model: str,
    system: str,
    user_msg: str,
    use_cache: bool = False,
) -> tuple[str, int, int, int]:
    """Wywołanie Anthropic API z opcjonalnym prompt cachingiem.

    Prompt caching w Anthropic:
    ─────────────────────────────
    1. Oznaczasz blok tekstu jako "cache_control": {"type": "ephemeral"}
    2. Pierwsze wywołanie: normalna cena (cache WRITE - nawet drożej, 1.25x)
    3. Kolejne wywołania z TYM SAMYM system promptem: 10x taniej (cache READ)
    4. Cache żyje 5 minut od ostatniego użycia

    Kiedy to się opłaca:
    - Masz DUŻY system prompt (np. 2000+ tokenów)
    - Wysyłasz WIELE zapytań z tym samym kontekstem
    - Przykład z lekcji: przetwarzanie 1000 faktur z tą samą instrukcją
    """
    system_blocks: list[dict] = [{"type": "text", "text": system}]
    if use_cache:
        system_blocks[0]["cache_control"] = {"type": "ephemeral"}

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=500,
        system=system_blocks,
        messages=[{"role": "user", "content": user_msg}],
    )

    usage = response.usage
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    return (response.content[0].text, usage.input_tokens, usage.output_tokens, cached)


# ── GŁÓWNA FUNKCJA ROUTERA ───────────────────────────────────────────────────


def run_task(
    task_name: str,
    system: str,
    user_msg: str,
    tier_override: ModelTier | None = None,    # składnia X | Y z Pythona 3.10+
    use_cache: bool = False,
) -> TaskResult:
    """Wykonaj zadanie z automatycznym routingiem modelu.

    Parametr tier_override pozwala wymusić konkretny tier -
    przydatne do porównywania kosztów (to samo zadanie na tanim vs drogim modelu).
    """
    tier = tier_override or classify_complexity(user_msg)
    config = MODELS[tier]

    start = time.time()

    if config.provider == "openai":
        response, inp, out = call_openai(config.name, system, user_msg)
        cached = 0
    else:
        response, inp, out, cached = call_anthropic(
            config.name, system, user_msg, use_cache
        )

    duration = (time.time() - start) * 1000
    cost = calculate_cost(config, inp, out, cached)

    return TaskResult(
        task_name=task_name,
        model_used=config.name,
        tier=tier,
        response=response,
        input_tokens=inp,
        output_tokens=out,
        cached_tokens=cached,
        cost_usd=cost,
        duration_ms=duration,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO 1: TOKENIZACJA - POLSKI vs ANGIELSKI
# ══════════════════════════════════════════════════════════════════════════════

def demo_tokenization():
    """Pokaż dlaczego polski tekst kosztuje więcej niż angielski.

    Tokenizery LLM (BPE - Byte Pair Encoding) są trenowane głównie
    na tekście angielskim. Polski tekst:
    - Używa znaków spoza ASCII (ą, ę, ś, ć, ź, ż, ó, ł, ń)
    - Ma dłuższe słowa (fleksja: przypadki, koniugacja)
    - Rzadziej występuje w danych treningowych tokenizera

    Efekt: to samo zdanie w PL zużywa ~50-70% więcej tokenów niż w EN.
    To bezpośrednio przekłada się na wyższy koszt.
    """
    print("\n" + "=" * 70)
    print("  DEMO 1: TOKENIZACJA — POLSKI vs ANGIELSKI")
    print("=" * 70)

    # Te zdania mówią to samo, ale kosztują inaczej
    samples = [
        (
            "Sztuczna inteligencja zmienia sposób w jaki pracujemy z dokumentami.",
            "Artificial intelligence is changing the way we work with documents.",
        ),
        (
            "Przetwarzanie języka naturalnego wymaga zrozumienia kontekstu wypowiedzi.",
            "Natural language processing requires understanding the context of speech.",
        ),
        (
            "Zoptymalizowaliśmy koszty przetwarzania faktur o dziewięćdziesiąt procent.",
            "We optimized invoice processing costs by ninety percent.",
        ),
    ]

    encoder = tiktoken.encoding_for_model("gpt-4o")

    total_pl, total_en = 0, 0
    for pl, en in samples:
        tokens_pl = len(encoder.encode(pl))
        tokens_en = len(encoder.encode(en))
        total_pl += tokens_pl
        total_en += tokens_en
        ratio = tokens_pl / tokens_en

        print(f"\n  PL: \"{pl}\"")
        print(f"      → {tokens_pl} tokenów")
        print(f"  EN: \"{en}\"")
        print(f"      → {tokens_en} tokenów")
        print(f"  Stosunek PL/EN: {ratio:.2f}x")

    overall = total_pl / total_en
    print(f"\n  ── Średnio polski tekst zużywa {overall:.0%} tokenów angielskiego")
    print(f"     To znaczy: {overall - 1:.0%} WIĘCEJ za to samo znaczenie.")
    print(f"     Przy dużej skali (miliony zapytań) to realna różnica w kosztach.\n")


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO 2: MODEL ROUTING - PROSTE vs ZŁOŻONE ZADANIA
# ══════════════════════════════════════════════════════════════════════════════

def demo_model_routing():
    """Pokaż jak routing obniża koszty bez utraty jakości.

    Trzy zadania o różnej złożoności:
    1. Klasyfikacja (proste)     → gpt-4o-mini   (najtańszy)
    2. Tłumaczenie (średnie)     → claude-haiku   (środkowy)
    3. Analiza strategiczna (złożone) → gpt-4o    (najdroższy)

    Na końcu: porównanie kosztów z routingiem vs "zawsze GPT-4o".
    """
    print("\n" + "=" * 70)
    print("  DEMO 2: MODEL ROUTING — DOPASOWANIE MODELU DO ZADANIA")
    print("=" * 70)

    # Wspólny system prompt - krótki i konkretny
    system = "Odpowiadaj zwięźle, po polsku, maksymalnie 2-3 zdania."

    tasks = [
        # (nazwa, zapytanie użytkownika)
        ("Klasyfikacja",
         "Sklasyfikuj ten email jako SPAM lub NIE-SPAM: "
         "'Wygrałeś iPhone 15! Kliknij tutaj aby odebrać nagrodę!'"),

        ("Tłumaczenie",
         "Przetłumacz na angielski: 'Zarządzanie kontekstem w systemach "
         "agentowych wymaga precyzyjnego doboru informacji przekazywanej modelowi.'"),

        ("Analiza",
         "Przeanalizuj: jakie są 3 najważniejsze ryzyka przy wdrażaniu "
         "systemu agentowego w firmie finansowej i dlaczego?"),
    ]

    results: list[TaskResult] = []
    routed_total_cost = 0.0
    expensive_total_cost = 0.0

    for task_name, user_msg in tasks:
        # ── Z routingiem (automatyczny dobór modelu)
        result = run_task(task_name, system, user_msg)
        results.append(result)
        routed_total_cost += result.cost_usd

        print(f"\n  ┌─ {task_name}")
        print(f"  │  Router wybrał: {result.model_used} ({result.tier.value})")
        print(f"  │  Tokeny: {result.input_tokens} in → {result.output_tokens} out")
        print(f"  │  Koszt:  ${result.cost_usd:.6f}")
        print(f"  │  Czas:   {result.duration_ms:.0f}ms")
        print(f"  │  Odpowiedź: {result.response[:120]}...")
        print(f"  └─")

        # ── To samo zadanie na GPT-4o (najdroższy) - do porównania
        expensive_result = run_task(
            task_name, system, user_msg,
            tier_override=ModelTier.EXPENSIVE,
        )
        expensive_total_cost += expensive_result.cost_usd

    # ── Podsumowanie oszczędności
    if expensive_total_cost > 0:
        savings = 1 - (routed_total_cost / expensive_total_cost)
    else:
        savings = 0

    print(f"\n  ── PODSUMOWANIE KOSZTÓW ──")
    print(f"     Z routingiem:      ${routed_total_cost:.6f}")
    print(f"     Zawsze GPT-4o:     ${expensive_total_cost:.6f}")
    print(f"     Oszczędność:       {savings:.0%}")
    print(f"\n     Przy 10 000 zapytań dziennie:")
    print(f"       Routing:   ${routed_total_cost * 10000:.2f}/dzień")
    print(f"       GPT-4o:    ${expensive_total_cost * 10000:.2f}/dzień")
    print(f"       Oszczędzasz: ${(expensive_total_cost - routed_total_cost) * 10000:.2f}/dzień\n")

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO 3: PROMPT CACHING (Anthropic)
# ══════════════════════════════════════════════════════════════════════════════

def demo_prompt_caching():
    """Pokaż jak prompt caching zmniejsza koszty powtarzalnych zapytań.

    Scenariusz: masz DUŻY system prompt (instrukcja do analizy faktur)
    i wysyłasz wiele zapytań z różnymi fakturami.

    Bez cachingu: płacisz za system prompt przy KAŻDYM zapytaniu.
    Z cachingiem: płacisz pełną cenę RAZ, potem 10x taniej.

    UWAGA: cache działa tylko gdy system prompt ma min. 1024 tokeny (Anthropic)
    i kolejne zapytania muszą mieć IDENTYCZNY tekst do cache'owanego punktu.
    """
    print("\n" + "=" * 70)
    print("  DEMO 3: PROMPT CACHING — OSZCZĘDNOŚĆ NA POWTARZALNYCH ZAPYTANIACH")
    print("=" * 70)

    # Duży system prompt (musi mieć 1024+ tokenów żeby cache zadziałał)
    # Symulujemy instrukcję do przetwarzania faktur
    system_prompt = """Jesteś ekspertem od analizy faktur. Twoim zadaniem jest wyciągnięcie
kluczowych informacji z podanej faktury i zwrócenie ich w ustrukturyzowanym formacie.

ZASADY ANALIZY:
1. Zawsze identyfikuj: numer faktury, datę wystawienia, termin płatności
2. Wyodrębnij dane sprzedawcy: nazwa, NIP, adres
3. Wyodrębnij dane nabywcy: nazwa, NIP, adres
4. Dla każdej pozycji na fakturze wyodrębnij: nazwa, ilość, cena jednostkowa, wartość netto, stawka VAT, wartość brutto
5. Oblicz i zweryfikuj sumę netto, sumę VAT, sumę brutto
6. Sprawdź czy kwoty się zgadzają (suma pozycji = suma na fakturze)
7. Zidentyfikuj walutę i metodę płatności
8. Jeśli faktura jest w walucie obcej, zanotuj kurs wymiany jeśli podany

FORMATY DANYCH:
- Daty: YYYY-MM-DD
- Kwoty: liczby z 2 miejscami po przecinku, bez separatorów tysięcy
- NIP: 10 cyfr bez myślników

WYKRYWANIE ANOMALII:
- Sprawdź czy NIP ma poprawną liczbę cyfr
- Sprawdź czy data wystawienia nie jest w przyszłości
- Sprawdź czy termin płatności jest po dacie wystawienia
- Sprawdź czy stawki VAT są standardowe (23%, 8%, 5%, 0%, ZW, NP)
- Sprawdź czy wartość brutto = netto + VAT dla każdej pozycji
- Jeśli faktura korygująca - zidentyfikuj numer faktury korygowanej

OBSŁUGIWANE TYPY DOKUMENTÓW:
- Faktura VAT
- Faktura korygująca
- Faktura proforma
- Nota korygująca
- Rachunek

FORMAT ODPOWIEDZI:
Odpowiedz w formacie JSON z następującymi polami:
{{
    "numer_faktury": "...",
    "typ_dokumentu": "faktura_vat|korygujaca|proforma|nota|rachunek",
    "data_wystawienia": "YYYY-MM-DD",
    "termin_platnosci": "YYYY-MM-DD",
    "sprzedawca": {{"nazwa": "...", "nip": "...", "adres": "..."}},
    "nabywca": {{"nazwa": "...", "nip": "...", "adres": "..."}},
    "pozycje": [{{"nazwa": "...", "ilosc": 0, "cena_netto": 0.00, "vat_procent": 23, "brutto": 0.00}}],
    "suma_netto": 0.00,
    "suma_vat": 0.00,
    "suma_brutto": 0.00,
    "waluta": "PLN",
    "metoda_platnosci": "przelew|gotowka|karta",
    "anomalie": ["lista wykrytych problemów"]
}}

Jeśli jakieś pole jest niedostępne, użyj null.
Zawsze odpowiadaj TYLKO poprawnym JSON-em, bez dodatkowego tekstu."""

    # Dwie różne faktury do przetworzenia TYM SAMYM system promptem
    invoices = [
        ("Faktura 1",
         "Faktura VAT nr FV/2025/001, wystawiona 2025-01-15, termin płatności 2025-02-14. "
         "Sprzedawca: Tech Solutions Sp. z o.o., NIP 5213456789, ul. Marszałkowska 10, Warszawa. "
         "Nabywca: Digital Corp S.A., NIP 1234567890, ul. Długa 5, Kraków. "
         "Pozycja 1: Licencja oprogramowania, 5 szt., 1000.00 PLN netto, VAT 23%. "
         "Płatność przelewem."),

        ("Faktura 2",
         "Faktura VAT nr FV/2025/002, wystawiona 2025-01-20, termin płatności 2025-02-19. "
         "Sprzedawca: Tech Solutions Sp. z o.o., NIP 5213456789, ul. Marszałkowska 10, Warszawa. "
         "Nabywca: Startup Lab Sp. z o.o., NIP 9876543210, ul. Krótka 3, Gdańsk. "
         "Pozycja 1: Konsultacje IT, 40 godz., 200.00 PLN netto/godz., VAT 23%. "
         "Pozycja 2: Hosting, 12 mies., 150.00 PLN netto/mies., VAT 23%. "
         "Płatność przelewem."),
    ]

    config = MODELS[ModelTier.MEDIUM]  # claude-haiku
    results: list[TaskResult] = []

    for i, (name, invoice_text) in enumerate(invoices):
        result = run_task(
            task_name=f"Cache: {name}",
            system=system_prompt,
            user_msg=invoice_text,
            tier_override=ModelTier.MEDIUM,
            use_cache=True,   # ← włączamy caching
        )
        results.append(result)

        is_cache_hit = result.cached_tokens > 0
        print(f"\n  ┌─ {name} {'(CACHE HIT ✓)' if is_cache_hit else '(cache write)'}")
        print(f"  │  Tokeny input:   {result.input_tokens}")
        print(f"  │  Z cache:        {result.cached_tokens}")
        print(f"  │  Tokeny output:  {result.output_tokens}")
        print(f"  │  Koszt:          ${result.cost_usd:.6f}")
        print(f"  │  Czas:           {result.duration_ms:.0f}ms")
        print(f"  └─")

    # Porównanie: ile kosztowałoby BEZ cachingu
    if len(results) == 2:
        actual_cost = sum(r.cost_usd for r in results)
        # Koszt bez cachingu = wszystkie tokeny input po normalnej cenie
        no_cache_cost = sum(
            calculate_cost(config, r.input_tokens, r.output_tokens, cached_tokens=0)
            for r in results
        )
        print(f"\n  ── EFEKT CACHINGU ──")
        print(f"     Z cachingiem:      ${actual_cost:.6f}")
        print(f"     Bez cachingu:      ${no_cache_cost:.6f}")
        if no_cache_cost > 0:
            print(f"     Oszczędność:       {1 - actual_cost / no_cache_cost:.0%}")
        print(f"\n     Przy 1000 faktur dziennie (ten sam system prompt):")
        print(f"       Bez cache:  ${no_cache_cost / 2 * 1000:.2f}/dzień")
        print(f"       Z cache:    ${actual_cost / 2 * 1000:.2f}/dzień")
        print(f"       (przybliżenie - pierwszy request bez cache, reszta z cache)\n")


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO 4: ESTYMACJA KOSZTÓW PRZED WYSŁANIEM
# ══════════════════════════════════════════════════════════════════════════════

def demo_cost_estimation():
    """Pokaż jak oszacować koszt ZANIM wyślesz zapytanie.

    Lekcja S01E01: "Trzeba odpowiedzieć sobie na pytanie:
    ile kontekstu faktycznie potrzebuję?"

    W praktyce: policz tokeny, pomnóż przez cenę, zdecyduj
    czy warto wysyłać cały dokument czy tylko fragment.
    """
    print("\n" + "=" * 70)
    print("  DEMO 4: ESTYMACJA KOSZTÓW PRZED WYSŁANIEM")
    print("=" * 70)

    # Symulacja: masz dokument i chcesz go przeanalizować
    document = """
    Raport kwartalny Q4 2024 - Dział Rozwoju Produktu

    1. Podsumowanie
    W czwartym kwartale 2024 roku zespół produktowy zakończył trzy kluczowe
    inicjatywy: wdrożenie systemu rekomendacji opartego na AI, migrację
    infrastruktury do chmury oraz redesign interfejsu użytkownika aplikacji
    mobilnej. Łączny budżet projektów wyniósł 2,4 mln PLN.

    2. System rekomendacji AI
    Wdrożony system wykorzystuje model transformer do personalizacji
    rekomendacji produktowych. Testy A/B wykazały wzrost konwersji o 23%
    w porównaniu do poprzedniego algorytmu opartego na regułach.
    Koszt infrastruktury ML: 45 000 PLN/miesiąc.

    3. Migracja do chmury
    Zakończono migrację 85% usług do AWS. Pozostałe 15% (systemy legacy)
    wymaga refaktoryzacji przed migracją, planowanej na Q1 2025.
    Oszczędności: 30% redukcja kosztów infrastruktury.

    4. Redesign aplikacji mobilnej
    Nowy interfejs zwiększył retencję użytkowników o 15% i średni czas
    sesji o 25%. NPS wzrósł z 42 do 67 punktów.
    """ * 3  # pomnożone 3x żeby symulować dłuższy dokument

    system = "Przeanalizuj raport i wyciągnij 5 kluczowych wniosków. Odpowiedz zwięźle."

    # Liczenie tokenów PRZED wysłaniem
    input_tokens = count_tokens_openai(system + document)

    # Estymacja output (zakładamy ~200 tokenów na odpowiedź)
    estimated_output = 200

    print(f"\n  Dokument: {len(document)} znaków → {input_tokens} tokenów")
    print(f"  Szacowany output: ~{estimated_output} tokenów")
    print(f"\n  ── Szacowany koszt per model ──")

    for tier, config in MODELS.items():
        est_cost = calculate_cost(config, input_tokens, estimated_output)
        monthly = est_cost * 1000 * 30  # 1000 dokumentów dziennie × 30 dni

        print(f"     {config.name:30s}  ${est_cost:.6f}/zapytanie"
              f"  →  ${monthly:.2f}/miesiąc (przy 1k dok/dzień)")

    # Decyzja: czy warto skrócić dokument?
    short_doc = document[:len(document) // 3]
    short_tokens = count_tokens_openai(system + short_doc)

    print(f"\n  ── A gdyby wysłać tylko 1/3 dokumentu? ──")
    print(f"     Pełny dokument:    {input_tokens} tokenów")
    print(f"     1/3 dokumentu:     {short_tokens} tokenów")
    print(f"     Oszczędność:       {1 - short_tokens / input_tokens:.0%} mniej tokenów")

    # Lekcja: czasem lepiej zrobić summarization taniego fragmentu
    # niż wysyłać cały dokument do drogiego modelu
    print(f"\n  💡 Strategia z lekcji: użyj taniego modelu (gpt-4o-mini) do streszczenia")
    print(f"     dużego dokumentu, a potem wyślij streszczenie do drogiego modelu.")
    print(f"     To dwuetapowe podejście jest tańsze niż wysłanie całości do GPT-4o.\n")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 70)
    print("  S01E01: MODEL ROUTER & ANALIZATOR KOSZTÓW")
    print("  Lekcja: Programowanie interakcji z modelem językowym")
    print("═" * 70)

    # Demo 1: Tokenizacja (offline, nie wymaga API)
    demo_tokenization()

    # Demo 2: Model routing (wymaga OpenAI + Anthropic API)
    demo_model_routing()

    # Demo 3: Prompt caching (wymaga Anthropic API)
    demo_prompt_caching()

    # Demo 4: Estymacja kosztów (offline, nie wymaga API)
    demo_cost_estimation()

    print("═" * 70)
    print("  KONIEC — przeczytaj komentarze w kodzie, tam jest wiedza!")
    print("═" * 70)
