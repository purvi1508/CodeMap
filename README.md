# CodeMap

> AI-Powered Code Architecture Analysis & Documentation Generator

CodeMap ingests any GitHub repository and automatically produces architecture diagrams, function summaries, and actionable insights — powered by LLMs. Whether you're navigating a legacy codebase, onboarding new developers, or just trying to understand what you inherited, CodeMap does the heavy lifting.

---

## Features

- 🔍 **Automatic code analysis** — extracts classes, functions, and module dependencies
- 🧠 **AI-generated function summaries** — plain-English explanations of what every function does
- 🏛️ **Architecture diagrams** — application structure, data flow, and deployment views
- 🔎 **Pattern detection** — identifies design patterns, anti-patterns, and architectural styles
- 🎨 **Icon-enriched Mermaid diagrams** — clean, visual, auto-rendered to PNG
- ♻️ **Self-healing diagrams** — broken Mermaid syntax is auto-fixed by the LLM

---

## How It Works

The pipeline runs in **7 sequential steps**:

### Step 1 — Ingest
Clones the target GitHub repository and reads all source files into memory, preparing them for analysis.

### Step 2 — Analyze
Parses the ingested code to extract:
- All **classes** and **functions**
- **Dependencies** between modules

A summary of discovered functions is saved to `codemap/function_summary.json`.

### Step 3 — Structural Diagrams
Generates diagrams purely from the code's structure — no AI involved at this stage. Diagrams are saved as `.mmd` (Mermaid) files, then cleaned up and enriched with icons automatically.

Output: `diagrams/`

### Step 4 — Function Summaries *(uses AI)*
Sends domain functions to an LLM in batches of 10 to generate plain-English descriptions of what each function does.

Output: `codemap/function_llm_summaries.json`

### Step 5 — Pattern Detection *(uses AI · ~2 calls)*
Analyzes the codebase for:
- **Design patterns** (e.g. factory, singleton)
- **Anti-patterns** (e.g. god classes, circular deps)
- **Architectural patterns** (e.g. layered, event-driven)

Output: `codemap/pattern_detection.json`

### Step 6 — Architecture Analysis *(uses AI · ~3 calls)*
Combines all prior outputs — code structure, function summaries, detected patterns, and structural diagrams — to produce a high-level architectural overview and recommendations.

Output: `codemap/architecture/`

### Step 7 — Render Diagrams
Converts all `.mmd` files (both structural and architectural) into **PNG images**. If a diagram has syntax errors, the renderer attempts to auto-heal it using an LLM before retrying.

---

## Outputs at a Glance

| File / Folder | Contents |
|---|---|
| `codemap/function_summary.json` | List of all discovered functions |
| `codemap/function_llm_summaries.json` | AI-generated description of each function |
| `codemap/pattern_detection.json` | Detected design and anti-patterns |
| `diagrams/` | Structural diagrams (`.mmd` + `.png`) |
| `codemap/architecture/` | Architecture diagrams + `architecture_plan.json` |

---

## AI Usage Summary

| Step | Purpose | Approx. LLM Calls |
|---|---|---|
| Step 4 | Function summaries | ~1 per 10 functions |
| Step 5 | Pattern detection | ~2 |
| Step 6 | Architecture analysis | ~3 |
| Step 7 | Diagram self-healing (if needed) | Varies |

---

## Example: `recursive-llm`

> Analyzed repo: [`ysz/recursive-llm`](https://github.com/ysz/recursive-llm)

### Pipeline Output

```
────────────────────────────────────────────────────
  Pipeline Complete
────────────────────────────────────────────────────

  System                  : recursive-llm
  Total time              : 84.3s
  Total LLM calls         : ~18

  Function list           : codemap/function_summary.json
  LLM summaries           : codemap/function_llm_summaries.json
  Pattern report          : codemap/pattern_detection.json

  Structural diagrams     : diagrams/
    ✓ call_graph_2.mmd
    ✓ class_0.mmd
    ✓ dependency_1.mmd

  Architecture            : codemap/architecture/
    ✓ application_architecture.mmd
    ✓ data_flow.mmd
    ✓ deployment_architecture.mmd
      architecture_plan.json

  Top recommendations:
    •  Extract prompt-building logic into a dedicated PromptBuilder class
    •  Add retry/backoff handling around LLM API calls
    •  Consider caching layer to avoid redundant LLM calls for identical inputs

  Security concerns:
    ⚠  API key passed via environment variable — ensure .env is gitignored
    ⚠  No input sanitization before passing user content to LLM
```

---

### Architecture Diagrams

#### Application Architecture
![Application Architecture](docs/images/application_architecture.png)

#### Data Flow
![Data Flow](docs/images/data_flow.png)

#### Deployment Architecture
![Deployment Architecture](docs/images/deployment_architecture.png)

---

### Structural Diagrams

#### Call Graph
![Call Graph](docs/images/call_graph_2.png)

#### Class Diagram
![Class Diagram](docs/images/class_0.png)

#### Dependency Graph
![Dependency Graph](docs/images/dependency_1.png)

---

### Detected Patterns

```json
{
  "design_patterns": [
    { "name": "Chain of Responsibility", "location": "llm/chain.py", "confidence": "high" },
    { "name": "Strategy", "location": "llm/models.py", "confidence": "medium" }
  ],
  "anti_patterns": [
    { "name": "God Function", "location": "main.py:run_pipeline", "severity": "medium" }
  ],
  "architectural_patterns": [
    { "name": "Pipeline / Chain", "confidence": "high" },
    { "name": "Prompt Engineering Layer", "confidence": "high" }
  ]
}
```

### Sample Function Summaries

```json
{
  "run_pipeline": "Entry point that orchestrates the full recursive LLM chain — initialises each stage, passes outputs downstream, and returns the final aggregated result.",
  "build_prompt": "Constructs a structured prompt string from a template and a dict of dynamic values; handles missing keys gracefully by substituting empty strings.",
  "call_llm": "Sends a prompt to the configured LLM provider, applies retry logic on rate-limit errors, and returns the raw text response.",
  "parse_response": "Extracts structured data from a raw LLM response string using regex heuristics; falls back to returning the full string if no structure is detected.",
  "merge_results": "Combines outputs from multiple LLM chain stages into a single unified dict, with later stages taking precedence on key conflicts."
}
```

---

## Roadmap

### v0.1.0 — Done
- [x] Basic code analysis

### v0.2.0 — Complete
- [x] LLM function summarization with batching and retry
- [x] Design pattern and anti-pattern detection
- [x] Production architecture diagrams (application, deployment, data flow)
- [x] Icon injection into Mermaid diagrams
- [x] Mermaid post-processing (syntax cleanup)
- [x] Full 7-step pipeline with timing and LLM call tracking

### v0.3.0 — Planned
- [ ] Multi-language support (JavaScript, TypeScript, Java, Go)
- [ ] Interactive web UI to explore diagrams and summaries
- [ ] GitHub Actions integration — run on every PR
- [ ] Incremental analysis — only re-analyze changed files
- [ ] Cost estimator — preview LLM call count before running