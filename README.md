# VERA AI Challenge — Implementation

This project implements a fully deterministic, rule-based message composition engine for the magicpin AI Challenge.

## Approach
Instead of relying on LLMs for composition (which can hallucinate, cost API credits, and be slow), this implementation uses a **Priority-Ranked Decision Engine** and a **Template-Based Composer** to generate high-compulsion messages.

### Key Components

1. **Context Store (`state.py`)**
   - Idempotent, version-controlled storage for the 4 contexts (Category, Merchant, Customer, Trigger).
   - In-memory state tracking for conversation turns, auto-reply detection, and suppression logic.

2. **Decision Engine (`decision_engine.py`)**
   - Ranks triggers strictly based on business priorities (e.g., `supply_alert` > `active_planning_intent` > `perf_dip`).
   - Resolves conflicts deterministically (picks the highest scored trigger per merchant).
   - Boosts scores based on merchant's context (e.g., if engaged in last 48h, or if an active offer matches).

3. **Voice Profiles (`voice_profiles.py`)**
   - Implements category-specific tone guidelines, vocabularies, and taboo filters.
   - Example: Uses "Dr. {Name}" for dentists with a peer-clinical tone, but "Hi {Name}" with emojis for salons.

4. **Message Composer (`compose.py`)**
   - Over 20 trigger-specific templates.
   - Injects verifiable specificity (numbers, metrics) directly from contexts to score high on Specificity and Merchant Fit.
   - Enforces single, low-friction CTAs (e.g., "Reply YES").

5. **Reply Handler (`reply_handler.py`)**
   - Detects auto-replies across multiple turns and gracefully backs off.
   - Transitions intent (if merchant says "let's do it", switches to action execution mode).
   - Handles hostile users by opting them out gracefully.

6. **FastAPI Bot (`bot.py`)**
   - Exposes all 5 endpoints required by the challenge harness (`/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`).

## Setup & Running

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn bot:app --host 0.0.0.0 --port 8080
   ```

3. Generate submission files from canonical test pairs:
   ```bash
   python generate_submission.py
   ```

## Scoring Strategy
- **Specificity**: Explicit injection of data (views, dates, active offers, counts).
- **Category Fit**: Filtered through `voice_profiles.py` taboo lists and category-specific language templates.
- **Merchant Fit**: Uses owner's name, performance metrics, and active offers.
- **Trigger Relevance**: Directly addresses the "why now" (the trigger event) in the opening sentence.
- **Engagement Compulsion**: Uses persuasion levers (loss aversion, social proof, low-effort execution).

## Determinism
This engine is 100% deterministic and stateless except for its in-memory ContextStore. The same input contexts always result in the exact same output. Latency per `tick` or `reply` is < 50ms.
