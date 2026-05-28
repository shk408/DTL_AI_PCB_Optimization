# AI-Assisted Design Optimization for PCBs and Sustainable Electronics

This is a final-year engineering project prototype for evaluating PCB and electronics sustainability during the design phase. It analyzes a Bill of Materials, parses Gerber ZIP packages, optionally enriches components from Robu.in, estimates end-of-life material recovery, and produces an explainable recyclability score from 0 to 100.

## Features

- BoM ingestion from CSV, Excel, or JSON.
- Component-level scoring for toxicity, recyclability, repairability, restricted substance risk, sourcing availability, obsolescence, and greener alternatives.
- Gerber ZIP analysis for board size, layer count, copper estimate, drill count, via density, component density, SMD ratio, edge placement, and disassembly difficulty.
- Optional placement/centroid file support.
- Robu.in enrichment layer with fuzzy search query creation, local cache, offline fallback, availability metadata, and a modular client design for future suppliers.
- End-of-life recovery estimate for copper, contacts, solder, FR4, plastics, metals, and batteries.
- Streamlit UI with uploads, manual PCB fallback fields, explanations, and CSV/JSON/PDF exports.
- Unit tests for ingestion, scoring, Gerber parsing, and recovery estimation.

## Project Structure

```text
.
├── app.py
├── pyproject.toml
├── requirements.txt
├── README.md
├── samples/
│   ├── sample_bom.csv
│   ├── sample_placement.csv
│   └── demo_gerbers/
├── src/pcb_sustainability/
│   ├── export.py
│   ├── gerber.py
│   ├── ingestion.py
│   ├── models.py
│   ├── recommendations.py
│   ├── recycling.py
│   ├── robu.py
│   ├── scoring.py
│   └── utils.py
└── tests/
```

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the UI:

```powershell
streamlit run app.py
```

Run tests:

```powershell
pytest
```

## GitHub and Streamlit Cloud Deployment

GitHub Pages cannot directly host this app because it is a Python Streamlit application, not a static HTML site. Use GitHub to host the source code, then deploy the app with Streamlit Community Cloud.

Recommended steps:

1. Create a new GitHub repository.
2. Upload these project files and folders: `app.py`, `README.md`, `requirements.txt`, `pyproject.toml`, `runtime.txt`, `.streamlit/`, `src/`, `samples/`, and `tests/`.
3. Do not upload `.venv/`, `.cache/`, `.codex_deps/`, `.pytest_cache/`, `outputs/`, or `__pycache__/`.
4. Go to Streamlit Community Cloud and create a new app from the GitHub repository.
5. Set the main file path to `app.py`.
6. Deploy.

Live Robu.in lookup may depend on the hosting provider's outbound network policy. The app still works with offline fallback enrichment when live lookup is disabled.

To create the sample Gerber ZIP for upload:

```powershell
Compress-Archive -Path samples\demo_gerbers\* -DestinationPath samples\demo_gerbers.zip -Force
```

## Example Usage

1. Start the Streamlit app.
2. Upload `samples/sample_bom.csv`.
3. Upload `samples/sample_placement.csv`.
4. Create and upload `samples/demo_gerbers.zip`, or use manual PCB fallback values.
5. Keep live Robu.in lookup disabled for offline demos, or enable it when internet access is available.
6. Click **Analyze design** and export the CSV, JSON, or PDF report.

## Scoring Logic

The prototype uses deterministic heuristics first, because this makes the demo explainable and repeatable.

The BoM score combines:

- toxicity risk: hazardous keywords such as lead, cadmium, mercury, brominated materials, PVC, and batteries;
- recyclability: modular connectors, copper/steel/aluminum, through-hole serviceability;
- repairability: package difficulty, with BGA/QFN/0201/glue/potting scored lower;
- restricted substance risk: hazardous terms reduced when RoHS, lead-free, halogen-free, or REACH appears;
- sourcing availability: improved by Robu.in availability metadata;
- obsolescence risk: terms such as obsolete, EOL, discontinued, and NRND;
- greener alternatives: compliance and safer-material signals.

The PCB design-for-recycling score combines:

- disassembly difficulty from layer count, via density, SMD ratio, component density, and battery presence;
- accessibility from edge placement and connector count;
- modularity from connectors and edge-serviceable parts;
- material recovery from copper estimate, layer count, and battery penalty.

The final recyclability score combines component sustainability, PCB design-for-recycling, and estimated end-of-life recovery.

## Robu.in Integration

`RobuClient` builds a search query from each BoM row, checks `.cache/robu_results.json`, and only calls Robu.in when live lookup is enabled. It extracts the best available title, category, manufacturer guess, package guess, datasheet link, availability text, price, similar component hints, and match confidence.

If the network is blocked, the page layout changes, or no result is found, the pipeline returns structured fallback data instead of failing the analysis. This keeps the academic demo reliable while making the supplier layer replaceable later with DigiKey, Mouser, LCSC, Octopart, or a formal API.

## ML Extension Points

`SustainabilityModel` in `scoring.py` defines the interface a future trained model can implement. The current `RuleBasedSustainabilityScorer` can be replaced with a classifier, ranking model, embedding search system, or LLM-assisted alternatives recommender without changing the Streamlit app.

## Notes

The Gerber parser is a practical prototype parser, not a certified CAM validation tool. It extracts measurable features from common RS-274X and Excellon text files and reports warnings when data is missing. This is intentional: the tool should be honest about uncertainty instead of faking design intelligence.
