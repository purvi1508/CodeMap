# src/ai/openai_analyzer.py

import json
import os
import re
import time
import random
from dataclasses import dataclass, field
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

@dataclass
class Service:
    name: str
    type: str                    # "internal" | "external" | "datastore" | "queue" | "gateway" | "worker"
    responsibility: str
    components: list[str]        = field(default_factory=list)
    technology: str              = ""
    exposed_api: list[str]       = field(default_factory=list)
    scalability_notes: str       = ""
    failure_modes: str           = ""


@dataclass
class DataFlow:
    from_service: str
    to_service: str
    label: str
    protocol: str
    direction: str
    data_shape: str = ""


@dataclass
class ArchitecturePlan:
    system_name:             str
    system_description:      str
    services:                list[Service]  = field(default_factory=list)
    data_flows:              list[DataFlow] = field(default_factory=list)
    external_dependencies:   list[str]      = field(default_factory=list)
    tech_stack:              list[str]      = field(default_factory=list)
    recommendations:         list[str]      = field(default_factory=list)
    security_concerns:       list[str]      = field(default_factory=list)
    scalability_bottlenecks: list[str]      = field(default_factory=list)

    # The 3 production diagrams
    application_architecture_diagram: str = ""   # services + microservices + boundaries
    deployment_architecture_diagram:  str = ""   # infra layers, containers, cloud
    data_flow_diagram:                str = ""   # sequence of a real end-to-end operation

    def to_dict(self) -> dict:
        return {
            "system_name":             self.system_name,
            "system_description":      self.system_description,
            "tech_stack":              self.tech_stack,
            "external_dependencies":   self.external_dependencies,
            "services":                [s.__dict__ for s in self.services],
            "data_flows":              [f.__dict__ for f in self.data_flows],
            "recommendations":         self.recommendations,
            "security_concerns":       self.security_concerns,
            "scalability_bottlenecks": self.scalability_bottlenecks,
            "diagrams": {
                "application_architecture": self.application_architecture_diagram,
                "deployment_architecture":  self.deployment_architecture_diagram,
                "data_flow":                self.data_flow_diagram,
            }
        }

    def save(self, output_dir: str | Path):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        with open(out / "architecture_plan.json", "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        diagrams = {
            "application_architecture.mmd": self.application_architecture_diagram,
            "deployment_architecture.mmd":  self.deployment_architecture_diagram,
            "data_flow.mmd":                self.data_flow_diagram,
        }
        saved = []
        for filename, content in diagrams.items():
            if content and content.strip():
                with open(out / filename, "w") as f:
                    f.write(content)
                saved.append(filename)

        print(f"  [OpenAIAnalyzer] Saved plan      → {out / 'architecture_plan.json'}")
        print(f"  [OpenAIAnalyzer] Saved diagrams  → {', '.join(saved)}")


# ---------------------------------------------------------------------------
# Analyzer — 3 LLM calls
# ---------------------------------------------------------------------------

class OpenAIAnalyzer:
    """
    Synthesizes ALL available artefacts into 3 production architecture diagrams.

    Diagram 1 — Application Architecture
    ──────────────────────────────────────
    A visual blueprint of the system's logical structure. Shows every
    internal service/microservice, the classes that compose it, boundaries
    between services, and all integration points to external systems.
    This is the diagram engineers point at during code reviews and
    system design discussions.

      Mermaid: `graph TB` with subgraphs per service, styled nodes by type,
               labelled arrows showing protocol and data shape.

    Diagram 2 — Deployment Architecture
    ─────────────────────────────────────
    Maps where each service runs. Shows infrastructure layers:
    Client → Gateway → Application Tier → Data Tier → External Services.
    Includes runtime environments (process / container / cloud function),
    replication/scaling notes, and network boundaries.

      Mermaid: `graph TB` with nested subgraphs per infrastructure zone.

    Diagram 3 — Data Flow
    ──────────────────────
    The primary happy-path end-to-end operation as a sequence diagram.
    Shows the exact sequence of calls, what data is exchanged at each step,
    and where async boundaries occur.

      Mermaid: `sequenceDiagram` with participants per service,
               sync (->>), async (-->>), and activation boxes.

    LLM calls
    ─────────
    Call 1 — Service decomposition  (classes + dep graph + call graph + patterns)
    Call 2 — Integration analysis   (service map + function summaries + call graph)
    Call 3 — All 3 diagrams         (full plan from calls 1 + 2)
    """

    MAX_RETRIES = 3
    BASE_DELAY  = 2.0

    # ── system prompts ─────────────────────────────────────────────────

    _SYSTEM_SERVICES = """
You are a principal software architect decomposing a codebase into logical services.

You will receive:
  1. A class inventory with methods and inheritance
  2. The module dependency graph (Mermaid)
  3. The class diagram (Mermaid)
  4. Detected design patterns and anti-patterns

Identify the LOGICAL SERVICES — bounded contexts that could each be owned by one team.
For each service name every class/module that belongs to it.
Also identify all external systems this codebase depends on.

For `type` use: "internal" | "external" | "datastore" | "queue" | "gateway" | "worker"

Respond ONLY with valid JSON — no markdown, no extra text:
{
  "system_name": "",
  "system_description": "",
  "tech_stack": [""],
  "external_dependencies": [""],
  "services": [
    {
      "name": "",
      "type": "internal|external|datastore|queue|gateway|worker",
      "responsibility": "",
      "components": ["class or module names"],
      "technology": "",
      "exposed_api": ["public method or endpoint names"],
      "scalability_notes": "",
      "failure_modes": ""
    }
  ]
}
""".strip()

    _SYSTEM_INTEGRATION = """
You are a principal software architect mapping integrations between services.

You will receive:
  1. The service map from the previous step
  2. The call graph (Mermaid) showing actual function-to-function calls
  3. Function summaries with inputs, outputs, and notes

Use the call graph to find REAL data flows. If a function in service A
calls a function in service B, that is an integration point.

Identify:
  - The protocol (sync function call, async, HTTP, file I/O, queue)
  - What data is exchanged (from function summaries)
  - Security concerns (exec/eval of untrusted input, missing auth, secrets in env)
  - Scalability bottlenecks (sync waits on LLM, unbounded recursion, no caching)
  - Architectural recommendations

Respond ONLY with valid JSON — no markdown, no extra text:
{
  "data_flows": [
    {
      "from_service": "",
      "to_service": "",
      "label": "",
      "protocol": "HTTP|gRPC|function call|async|file I/O|event|queue",
      "direction": "sync|async|bidirectional",
      "data_shape": ""
    }
  ],
  "security_concerns": [""],
  "scalability_bottlenecks": [""],
  "recommendations": [""]
}
""".strip()

    _SYSTEM_DIAGRAMS = """
You are a principal software architect generating production Mermaid diagrams.

You will receive the complete architecture plan: services, data flows,
components, tech stack, external dependencies, security concerns,
scalability bottlenecks, and recommendations.

Generate exactly 3 diagrams:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIAGRAM 1 — APPLICATION ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is the visual blueprint engineers point at in design reviews.
Show the full logical structure of the system.

Use `graph TB` with:
- One `subgraph` per internal service, labeled with the service name and responsibility
- Inside each subgraph: individual nodes for every class/module that belongs to it
  Use shapes to distinguish types:
    Classes/modules    → rectangular  ServiceName[ClassName]
    Datastores         → cylinder     DB[(Database)]
    Queues             → stadium      Q([Queue])
    External services  → rounded      Ext(ExternalService)
- Arrows between subgraphs (or to external nodes) for every integration:
  Label every arrow with  protocol: data_shape
- Group external systems in a separate subgraph labeled "External Systems"
- Add a Mermaid `classDef` section with styles:
    internal  → blue fill
    external  → orange fill
    datastore → green fill
    queue     → purple fill
    gateway   → teal fill
  Apply via `class NodeName internal` etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIAGRAM 2 — DEPLOYMENT ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Show WHERE and HOW the system runs in production.

Use `graph TB` with nested subgraphs for infrastructure zones:

  subgraph CLIENT_TIER [Client Tier]
  subgraph APP_TIER    [Application Tier]
  subgraph DATA_TIER   [Data Tier]
  subgraph EXTERNAL    [External Services]

Inside each zone place the services that run there.
For each service node include:
  - Runtime (Python process / Docker container / Lambda / etc.)
  - Replicas or scaling strategy if inferable
Show network boundaries with dashed subgraph borders where applicable.
Label all arrows with protocol and port where known.
Add `classDef` styles:
    process   → light blue
    container → blue
    cloud     → purple
    external  → orange

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIAGRAM 3 — DATA FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The primary happy-path operation end-to-end.
Pick the most important user-facing operation in the system.

Use `sequenceDiagram` with:
- One participant per service (use short names)
- Mark external participants with <<external>>
- Sync calls:   ServiceA ->> ServiceB: label
- Async calls:  ServiceA -->> ServiceB: label
- Responses:    ServiceB -->> ServiceA: label
- Use activate/deactivate to show where work is happening
- Add a Note over ServiceX: for important processing steps
- Show the full round-trip including error paths with alt/else blocks
  where relevant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rules for ALL diagrams:
  - No () inside [] node labels — use plain text only
  - No `break` statements
  - No placeholder comments like %% add more here
  - Every node and arrow must be concrete and named from the actual plan
  - Diagrams must be valid standalone Mermaid that renders without errors

Respond ONLY with valid JSON — no markdown, no extra text:
{
  "application_architecture_diagram": "full mermaid source",
  "deployment_architecture_diagram":  "full mermaid source",
  "data_flow_diagram":                "full mermaid source"
}
""".strip()

    # ──────────────────────────────────────────────────────────────────

    def __init__(self, retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
        self.retries    = retries
        self.base_delay = base_delay

        raw_headers = os.getenv("LLM_DEFAULT_HEADERS", "{}")
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-5.1"),
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            default_headers=json.loads(raw_headers),
            temperature=0,
        )

    # ── public entry point ─────────────────────────────────────────────

    def analyze(
        self,
        analysis_result,
        summaries_path:  str | Path | None = None,
        patterns_path:   str | Path | None = None,
        diagrams_dir:    str | Path | None = None,
        output_dir:      str | Path | None = None,
    ) -> ArchitecturePlan:
        summaries = self._load_json(summaries_path)
        patterns  = self._load_json(patterns_path)
        mmds      = self._load_mmd_files(diagrams_dir)

        # ── call 1: service decomposition ──────────────────────────────
        print("  [OpenAIAnalyzer] Call 1/3 — service decomposition...")
        services_raw = self._call_llm(
            system=self._SYSTEM_SERVICES,
            user=self._prompt_services(analysis_result, patterns, mmds),
        )

        # ── call 2: integration analysis ───────────────────────────────
        print("  [OpenAIAnalyzer] Call 2/3 — integration analysis...")
        integration_raw = self._call_llm(
            system=self._SYSTEM_INTEGRATION,
            user=self._prompt_integration(services_raw, summaries, mmds),
        )

        # ── call 3: all 3 diagrams ──────────────────────────────────────
        print("  [OpenAIAnalyzer] Call 3/3 — generating 3 production diagrams...")
        combined = {**services_raw, **integration_raw}
        diagrams_raw = self._call_llm(
            system=self._SYSTEM_DIAGRAMS,
            user=(
                "Generate the 3 production architecture diagrams "
                "for this system plan:\n\n"
                f"```json\n{json.dumps(combined, indent=2)}\n```"
            ),
        )

        plan = self._assemble(services_raw, integration_raw, diagrams_raw)

        if output_dir:
            plan.save(output_dir)

        self._print_summary(plan)
        return plan

    # ── prompt builders ────────────────────────────────────────────────

    def _prompt_services(self, ar, patterns: dict, mmds: dict) -> str:
        parts = []

        parts.append(f"## Class inventory ({len(ar.all_classes)} classes)\n")
        for cls in ar.all_classes:
            bases   = getattr(cls, "base_classes", []) or []
            methods = getattr(cls, "methods", [])      or []
            line    = f"### {cls.name}"
            if bases:
                line += f" extends {', '.join(str(b) for b in bases)}"
            line += f"\nFile: {getattr(cls, 'file_path', 'unknown')}"
            if methods:
                line += f"\nMethods: {', '.join(m.name for m in methods)}"
            parts.append(line)

        parts.append(f"\n## Module dependencies\n")
        for dep in ar.dependencies:
            parts.append(f"- {dep}")

        if mmds.get("dependency"):
            parts.append("\n## Dependency graph (Mermaid)\n```\n" + mmds["dependency"] + "\n```")

        if mmds.get("class"):
            parts.append("\n## Class diagram (Mermaid)\n```\n" + mmds["class"] + "\n```")

        if patterns:
            parts.append("\n## Detected patterns\n")
            for ptype in ("architectural_patterns", "design_patterns", "anti_patterns"):
                items = patterns.get(ptype, [])
                if items:
                    parts.append(f"\n### {ptype.replace('_', ' ').title()}")
                    for p in items:
                        parts.append(
                            f"- **{p.get('pattern_name','')}** "
                            f"[{p.get('confidence','')}] "
                            f"@ {p.get('location','')}: {p.get('evidence','')}"
                        )
            if patterns.get("summary"):
                parts.append(f"\n### Summary\n{patterns['summary']}")

        return "\n".join(parts)

    def _prompt_integration(self, services_raw: dict, summaries: dict, mmds: dict) -> str:
        parts = []

        parts.append("## Service map\n```json")
        parts.append(json.dumps(services_raw, indent=2))
        parts.append("```")

        if mmds.get("call_graph"):
            parts.append("\n## Call graph (actual function calls)\n```")
            parts.append(mmds["call_graph"])
            parts.append("```")

        if summaries:
            domain = {
                k: v for k, v in summaries.items()
                if not k.startswith("test_") and not k.startswith("mock_")
            }
            parts.append(f"\n## Function summaries ({len(domain)} domain functions)\n")
            for name, s in list(domain.items())[:60]:
                if isinstance(s, dict):
                    parts.append(
                        f"**{name}**: {s.get('purpose', '')} | "
                        f"inputs: {s.get('inputs', '')} | "
                        f"outputs: {s.get('outputs', '')} | "
                        f"notes: {s.get('notes', '')}"
                    )
                else:
                    parts.append(f"**{name}**: {s}")

        return "\n".join(parts)

    # ── loaders ────────────────────────────────────────────────────────

    def _load_mmd_files(self, diagrams_dir: str | Path | None) -> dict:
        result = {"call_graph": "", "class": "", "dependency": ""}
        if not diagrams_dir:
            return result
        d = Path(diagrams_dir)
        if not d.exists():
            print(f"  [OpenAIAnalyzer] diagrams_dir not found: {d}")
            return result
        for mmd_file in d.glob("*.mmd"):
            name = mmd_file.stem.lower()
            try:
                content = mmd_file.read_text(encoding="utf-8").strip()
            except Exception as e:
                print(f"  [OpenAIAnalyzer] Could not read {mmd_file}: {e}")
                continue
            if "call" in name:
                result["call_graph"] = content
                print(f"  [OpenAIAnalyzer] Loaded call graph   → {mmd_file.name}")
            elif "class" in name:
                result["class"]      = content
                print(f"  [OpenAIAnalyzer] Loaded class diagram → {mmd_file.name}")
            elif "depend" in name:
                result["dependency"] = content
                print(f"  [OpenAIAnalyzer] Loaded dep graph     → {mmd_file.name}")
        return result

    @staticmethod
    def _load_json(path: str | Path | None) -> dict:
        if not path:
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            print(f"  [OpenAIAnalyzer] Could not load {path}: {e}")
            return {}

    # ── assembler ──────────────────────────────────────────────────────

    def _assemble(self, services_raw: dict, integration_raw: dict, diagrams_raw: dict) -> ArchitecturePlan:
        services = []
        for s in services_raw.get("services", []):
            try:
                services.append(Service(
                    name=              s.get("name", ""),
                    type=              s.get("type", "internal"),
                    responsibility=    s.get("responsibility", ""),
                    components=        s.get("components", []),
                    technology=        s.get("technology", ""),
                    exposed_api=       s.get("exposed_api", []),
                    scalability_notes= s.get("scalability_notes", ""),
                    failure_modes=     s.get("failure_modes", ""),
                ))
            except Exception:
                pass

        flows = []
        for f in integration_raw.get("data_flows", []):
            try:
                flows.append(DataFlow(
                    from_service= f.get("from_service", ""),
                    to_service=   f.get("to_service", ""),
                    label=        f.get("label", ""),
                    protocol=     f.get("protocol", "function call"),
                    direction=    f.get("direction", "sync"),
                    data_shape=   f.get("data_shape", ""),
                ))
            except Exception:
                pass

        return ArchitecturePlan(
            system_name=              services_raw.get("system_name",            "System"),
            system_description=       services_raw.get("system_description",     ""),
            services=                 services,
            data_flows=               flows,
            external_dependencies=    services_raw.get("external_dependencies",  []),
            tech_stack=               services_raw.get("tech_stack",             []),
            recommendations=          integration_raw.get("recommendations",       []),
            security_concerns=        integration_raw.get("security_concerns",     []),
            scalability_bottlenecks=  integration_raw.get("scalability_bottlenecks", []),
            application_architecture_diagram = diagrams_raw.get("application_architecture_diagram", ""),
            deployment_architecture_diagram  = diagrams_raw.get("deployment_architecture_diagram",  ""),
            data_flow_diagram                = diagrams_raw.get("data_flow_diagram",                ""),
        )

    # ── llm with retry ─────────────────────────────────────────────────

    def _call_llm(self, system: str, user: str) -> dict:
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ]
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.llm.invoke(messages)
                return self._parse_json(response.content)
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    delay = self.BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    print(f"    Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    print(f"    All {self.retries} attempts failed: {e}")
        return {}

    @staticmethod
    def _parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            clean = re.sub(r"```json|```", "", content).strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                print("    Warning: could not parse LLM response as JSON.")
                return {}

    # ── summary printer ────────────────────────────────────────────────

    @staticmethod
    def _print_summary(plan: ArchitecturePlan):
        print(f"\n  System      : {plan.system_name}")
        print(f"  Description : {plan.system_description}")
        print(f"\n  Services ({len(plan.services)})")
        for s in plan.services:
            tag = f"[{s.type}]"
            print(f"    {tag:12} {s.name:30} {s.responsibility[:55]}")
        print(f"\n  Data flows  : {len(plan.data_flows)}")
        print(f"  Tech stack  : {', '.join(plan.tech_stack)}")

        if plan.security_concerns:
            print("\n  Security concerns:")
            for c in plan.security_concerns:
                print(f"    ⚠  {c}")
        if plan.scalability_bottlenecks:
            print("\n  Scalability bottlenecks:")
            for b in plan.scalability_bottlenecks:
                print(f"    ⚡ {b}")
        if plan.recommendations:
            print("\n  Recommendations:")
            for r in plan.recommendations:
                print(f"    •  {r}")

        diagrams_ok = sum(1 for d in [
            plan.application_architecture_diagram,
            plan.deployment_architecture_diagram,
            plan.data_flow_diagram,
        ] if d and d.strip())
        print(f"\n  Diagrams generated: {diagrams_ok}/3")