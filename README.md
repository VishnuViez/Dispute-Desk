# DisputeDesk

DisputeDesk is a prototype AI agent that helps a bank's card dispute analyst investigate credit and debit card disputes. Given a customer's complaint, it picks the card-network reason code, checks deadlines, gathers evidence through backend tools, and recommends one of four outcomes (file chargeback, deny, request more info, or escalate) with a confidence score and the rule it relied on. A human analyst always makes the final decision.

Built for the IBM SkillsBuild AI Experiential Learning Lab (US Fall 2026), track: Revolutionizing Banking & Financial Services.

## Setup

**1. Create a virtual environment**

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

**2. Install requirements**

```bash
pip install -r requirements.txt
```

**3. Generate synthetic data**

```bash
python data/generate_data.py
```

**4. Start the API**

```bash
# macOS / Linux
uvicorn backend.app.main:app --reload

# Windows
uvicorn backend.app.main:app --reload
```

The API will be available at http://127.0.0.1:8000. Interactive docs at http://127.0.0.1:8000/docs.

**5. Run tests**

```bash
pytest
```

## Tools API

<!-- Tool endpoint documentation will be added here as endpoints are implemented -->
