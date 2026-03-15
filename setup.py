from src.ingest import CodeIngestor
from src.analyzers import CodeAnalyzer
from src.diagram_generators import DiagramGenerator
from src.ai import FunctionSummarizer, PatternDetector, OpenAIAnalyzer
from src.ai.mmd_postprocessor import MmdPostProcessor
from src.ai.mmd_icon_injector import MmdIconInjector
from src.ai.mmd_renderer import MmdRenderer
from dotenv import load_dotenv
from pathlib import Path
import json
import time

load_dotenv()

_HERE        = Path(__file__).parent
CODEMAP      = _HERE / "codemap"
DIAGRAMS_DIR = _HERE / "diagrams"
ARCH_DIR     = CODEMAP / "architecture"
ICON_JSON    = _HERE / "codemap" / "icon_link.json"

CODEMAP.mkdir(exist_ok=True)
DIAGRAMS_DIR.mkdir(exist_ok=True)
ARCH_DIR.mkdir(exist_ok=True)

postprocessor  = MmdPostProcessor()
icon_injector  = MmdIconInjector(ICON_JSON)
renderer       = MmdRenderer(output_format="png", width=2400)
pipeline_start = time.time()


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── STEP 1: INGEST ────────────────────────────────────────────────────────
section("Step 1 / 7 — Ingest")
ingestor  = CodeIngestor()
ingestion = ingestor.ingest("https://github.com/ysz/recursive-llm.git")
print("  Done.")

# ── STEP 2: ANALYZE ───────────────────────────────────────────────────────
section("Step 2 / 7 — Analyze")
analyzer = CodeAnalyzer()
result   = analyzer.analyze(ingestion)

print(f"  Classes:      {len(result.all_classes)}")
print(f"  Functions:    {len(result.all_functions)}")
print(f"  Dependencies: {len(result.dependencies)}")

with open(CODEMAP / "function_summary.json", "w") as f:
    json.dump({
        "function_count": len(result.all_functions),
        "function_names": [func.name for func in result.all_functions]
    }, f, indent=2)
print(f"  Saved → {CODEMAP / 'function_summary.json'}")

# ── STEP 3: STRUCTURAL DIAGRAMS (no LLM) ─────────────────────────────────
section("Step 3 / 7 — Structural Diagrams")
report    = analyzer.generate_full_report(ingestion)
generator = DiagramGenerator()
diagrams  = generator.generate_all(result)
diagrams.save_all(str(DIAGRAMS_DIR))

patched  = postprocessor.process_dir(DIAGRAMS_DIR)
injected = icon_injector.process_dir(DIAGRAMS_DIR)
print(f"  Saved    → {DIAGRAMS_DIR}")
print(f"  Cleaned  → {len(patched)} file(s) patched")
print(f"  Icons    → {len(injected)} file(s) updated")

# ── STEP 4: FUNCTION SUMMARIES (LLM) ─────────────────────────────────────
section("Step 4 / 7 — Function Summaries (LLM)")
llm_call_count  = 0
domain_fn_count = sum(
    1 for f in result.all_functions
    if not f.name.startswith("test_") and not f.name.startswith("mock_")
)
expected_batches = (domain_fn_count // 10) + 1
print(f"  {len(result.all_functions)} total functions → {domain_fn_count} domain functions")
print(f"  ~{expected_batches} LLM calls (batch size 10)")

summarizer = FunctionSummarizer(batch_size=10)
summarizer.summarize(
    result,
    output_path=CODEMAP / "function_llm_summaries.json",
)
llm_call_count += expected_batches
print(f"  Saved → {CODEMAP / 'function_llm_summaries.json'}")

# ── STEP 5: PATTERN DETECTION (LLM · 2 calls) ────────────────────────────
section("Step 5 / 7 — Pattern Detection (LLM · 2 calls)")
detector = PatternDetector()
patterns = detector.detect(
    result,
    output_path=CODEMAP / "pattern_detection.json",
)
llm_call_count += 2
print(f"  Saved → {CODEMAP / 'pattern_detection.json'}")
print(f"  Design patterns      : {len(patterns.design_patterns)}")
print(f"  Anti-patterns        : {len(patterns.anti_patterns)}")
print(f"  Architectural        : {len(patterns.architectural_patterns)}")

# ── STEP 6: ARCHITECTURE ANALYSIS (LLM · 3 calls) ────────────────────────
section("Step 6 / 7 — Architecture Analysis (LLM · 3 calls)")
arch_analyzer = OpenAIAnalyzer()
plan = arch_analyzer.analyze(
    analysis_result = result,
    summaries_path  = CODEMAP / "function_llm_summaries.json",
    patterns_path   = CODEMAP / "pattern_detection.json",
    diagrams_dir    = DIAGRAMS_DIR,
    output_dir      = ARCH_DIR,
)
llm_call_count += 3

arch_patched  = postprocessor.process_dir(ARCH_DIR)
arch_injected = icon_injector.process_dir(ARCH_DIR)
print(f"  Cleaned  → {len(arch_patched)} architecture diagram(s) patched")
print(f"  Icons    → {len(arch_injected)} architecture diagram(s) updated")

# ── STEP 7: RENDER .mmd → PNG (with LLM self-healing) ────────────────────
section("Step 7 / 7 — Render Diagrams to PNG")
struct_results = renderer.render_dir(DIAGRAMS_DIR)
arch_results   = renderer.render_dir(ARCH_DIR)

# Track extra LLM calls used during healing
heal_calls = sum(len(r["healed"]) for r in [struct_results, arch_results])
llm_call_count += heal_calls

for label, r in [("Structural", struct_results), ("Architecture", arch_results)]:
    for p in r["healed"]:
        print(f"  ♻  {label}: healed {p.name}  (diff: {p.stem}.mmd.bak)")
    for p in r["failed"]:
        print(f"  ✗  {label}: failed {p.name}  (original: {p.stem}.mmd.bak)")

# ── PIPELINE SUMMARY ──────────────────────────────────────────────────────
elapsed = time.time() - pipeline_start
section("Pipeline Complete")

print(f"  {'System':<24}: {plan.system_name}")
print(f"  {'Total time':<24}: {elapsed:.1f}s")
print(f"  {'Total LLM calls':<24}: ~{llm_call_count}")
print()
print(f"  {'Function list':<24}: {CODEMAP / 'function_summary.json'}")
print(f"  {'LLM summaries':<24}: {CODEMAP / 'function_llm_summaries.json'}")
print(f"  {'Pattern report':<24}: {CODEMAP / 'pattern_detection.json'}")
print()
print(f"  {'Structural diagrams':<24}: {DIAGRAMS_DIR}")
for f in sorted(DIAGRAMS_DIR.glob("*.mmd")):
    png = f.with_suffix(".png")
    tag = "✓" if png.exists() else "✗"
    print(f"    {tag} {f.name}")
print()
print(f"  {'Architecture':<24}: {ARCH_DIR}")
for f in sorted(ARCH_DIR.glob("*.mmd")):
    png = f.with_suffix(".png")
    tag = "✓" if png.exists() else "✗"
    print(f"    {tag} {f.name}")
print(f"      architecture_plan.json")
print()
if plan.recommendations:
    print("  Top recommendations:")
    for r in plan.recommendations[:3]:
        print(f"    •  {r}")
if plan.security_concerns:
    print("  Security concerns:")
    for c in plan.security_concerns[:3]:
        print(f"    ⚠  {c}")