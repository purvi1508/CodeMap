# src/ai/pattern_detector.py

import json
import os
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
class PatternMatch:
    pattern_name: str       # e.g. "Singleton", "God Class"
    pattern_type: str       # "design_pattern" | "anti_pattern" | "architectural"
    confidence: str         # "high" | "medium" | "low"
    location: str           # file / class / function where found
    evidence: str           # what in the code triggered detection
    suggestion: str         # actionable recommendation


@dataclass
class PatternDetectionResult:
    design_patterns:        list[PatternMatch] = field(default_factory=list)
    anti_patterns:          list[PatternMatch] = field(default_factory=list)
    architectural_patterns: list[PatternMatch] = field(default_factory=list)
    summary: str = ""

    @property
    def all_patterns(self) -> list[PatternMatch]:
        return self.design_patterns + self.anti_patterns + self.architectural_patterns

    @property
    def has_anti_patterns(self) -> bool:
        return bool(self.anti_patterns)

    def to_dict(self) -> dict:
        return {
            "design_patterns":        [p.__dict__ for p in self.design_patterns],
            "anti_patterns":          [p.__dict__ for p in self.anti_patterns],
            "architectural_patterns": [p.__dict__ for p in self.architectural_patterns],
            "summary":                self.summary,
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class PatternDetector:
    """
    Detects design patterns, anti-patterns, and architectural patterns
    from a CodeAnalyzer result using exactly 2 LLM calls:

      Call 1 — structural snapshot  →  class + dependency patterns
      Call 2 — function behaviour   →  behavioural + anti-patterns + summary

    Usage:
        detector = PatternDetector()
        result   = detector.detect(analysis_result)
        result.save("codemap/pattern_detection.json")
    """

    MAX_FUNCTIONS_IN_PROMPT = 40
    MAX_RETRIES = 3
    BASE_DELAY  = 2.0


    _SYSTEM_STRUCTURAL = """
You are a senior software architect reviewing a Python codebase.
You will receive a structural snapshot: classes, their methods, base classes,
and module-level dependencies.

Identify ONLY patterns that are clearly visible from structure alone:
  - Architectural patterns  (Pipeline, MVC, Repository, Service Layer, etc.)
  - Structural design patterns (Singleton, Factory, Composite, Decorator, etc.)
  - Structural anti-patterns (God Class, Circular Dependency, Shotgun Surgery, etc.)

Respond ONLY with valid JSON in this exact shape — no markdown, no extra text:
{
  "design_patterns":        [ { "pattern_name": "", "pattern_type": "design_pattern",   "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ],
  "anti_patterns":          [ { "pattern_name": "", "pattern_type": "anti_pattern",     "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ],
  "architectural_patterns": [ { "pattern_name": "", "pattern_type": "architectural",    "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ]
}
""".strip()

    _SYSTEM_BEHAVIOURAL = """
You are a senior software architect reviewing a Python codebase.
You will receive a behavioural snapshot: top-level functions with their
signatures, docstrings, and source code (where available), plus a
call-graph summary.

Identify patterns visible from behaviour and data-flow:
  - Behavioural design patterns (Strategy, Observer, Command, Chain of Responsibility, etc.)
  - Behavioural anti-patterns (Feature Envy, Long Method, Magic Numbers, etc.)
  - Any additional architectural observations not derivable from structure alone

Also write a one-paragraph executive summary of the overall architecture.

Respond ONLY with valid JSON in this exact shape — no markdown, no extra text:
{
  "design_patterns":        [ { "pattern_name": "", "pattern_type": "design_pattern", "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ],
  "anti_patterns":          [ { "pattern_name": "", "pattern_type": "anti_pattern",   "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ],
  "architectural_patterns": [ { "pattern_name": "", "pattern_type": "architectural",  "confidence": "high|medium|low", "location": "", "evidence": "", "suggestion": "" } ],
  "summary": ""
}
""".strip()


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

    # ------------------------------------------------------------------ #
    # Public entry point — 2 LLM calls total                              #
    # ------------------------------------------------------------------ #

    def detect(self, analysis_result, output_path: str | Path | None = None) -> PatternDetectionResult:
        """
        Args:
            analysis_result : object returned by CodeAnalyzer.analyze()
            output_path     : optional path to save pattern_detection.json

        Returns:
            PatternDetectionResult
        """
        print("  [PatternDetector] Call 1/2 — structural patterns...")
        structural_raw = self._call_llm(
            system=self._SYSTEM_STRUCTURAL,
            user=self._build_structural_prompt(analysis_result),
        )

        print("  [PatternDetector] Call 2/2 — behavioural patterns + summary...")
        behavioural_raw = self._call_llm(
            system=self._SYSTEM_BEHAVIOURAL,
            user=self._build_behavioural_prompt(analysis_result),
        )

        result = self._merge(structural_raw, behavioural_raw)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"  [PatternDetector] Saved → {path}")

        self._print_summary(result)
        return result

    # ------------------------------------------------------------------ #
    # Prompt builders                                                      #
    # ------------------------------------------------------------------ #

    def _build_structural_prompt(self, ar) -> str:
        lines = ["## Classes\n"]
        for cls in ar.all_classes:
            bases   = getattr(cls, "base_classes", []) or []
            methods = getattr(cls, "methods", [])      or []
            line = f"- **{cls.name}**"
            if bases:
                line += f" extends {', '.join(bases)}"
            if methods:
                line += f"\n  methods: {', '.join(m.name for m in methods)}"
            lines.append(line)

        lines.append(f"\n## Module Dependencies ({len(ar.dependencies)})\n")
        for dep in ar.dependencies:
            lines.append(f"- {dep}")

        return "\n".join(lines)

    def _build_behavioural_prompt(self, ar) -> str:
        # Filter out test functions — halves token usage, improves quality
        domain_fns = [
            f for f in ar.all_functions
            if not f.name.startswith("test_")
            and "/tests/" not in getattr(f, "file_path", "")
            and "\\tests\\" not in getattr(f, "file_path", "")
        ]

        # Cap at MAX_FUNCTIONS_IN_PROMPT — prioritise functions with source
        with_source    = [f for f in domain_fns if self._get_source(f)]
        without_source = [f for f in domain_fns if not self._get_source(f)]
        selected = (with_source + without_source)[:self.MAX_FUNCTIONS_IN_PROMPT]

        total   = len(ar.all_functions)
        skipped = total - len(selected)

        lines = [
            f"## Functions  (showing {len(selected)} of {total} total"
            + (f", {skipped} test/excess functions omitted" if skipped else "")
            + ")\n"
        ]

        for fn in selected:
            class_tag = getattr(fn, "class_name", None)
            header    = f"### {fn.name}"
            if class_tag:
                header += f" (method of {class_tag})"
            header += f"  —  {getattr(fn, 'file_path', 'unknown')}"

            lines.append(header)
            lines.append(f"Signature : {getattr(fn, 'signature', '')}")
            lines.append(f"Docstring : {getattr(fn, 'docstring', '') or 'None'}")
            source = self._get_source(fn)
            if source:
                lines.append(f"```python\n{source}\n```")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # LLM call with retry + exponential backoff                           #
    # ------------------------------------------------------------------ #

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
                    delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    print(f"    Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    print(f"    All {self.retries} attempts failed: {e}")

        return {}   
    
    @staticmethod
    def _get_source(func) -> str:
        return (
            getattr(func, "source_code", "")
            or getattr(func, "source", "")
            or getattr(func, "body", "")
        )

    @staticmethod
    def _parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            clean = content.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                print("    Warning: could not parse LLM response as JSON.")
                return {}

    @staticmethod
    def _to_matches(raw: list) -> list[PatternMatch]:
        matches = []
        for item in raw:
            try:
                matches.append(PatternMatch(**item))
            except (TypeError, KeyError):
                pass
        return matches

    def _merge(self, structural: dict, behavioural: dict) -> PatternDetectionResult:
        """Combine results from both LLM calls, deduplicating by pattern_name."""
        seen: set[str] = set()
        design, anti, arch = [], [], []

        def add(raw_list: list, bucket: list):
            for item in raw_list:
                key = item.get("pattern_name", "").lower()
                if key and key not in seen:
                    seen.add(key)
                    try:
                        bucket.append(PatternMatch(**item))
                    except (TypeError, KeyError):
                        pass

        for src in (structural, behavioural):
            add(src.get("design_patterns",        []), design)
            add(src.get("anti_patterns",          []), anti)
            add(src.get("architectural_patterns", []), arch)

        return PatternDetectionResult(
            design_patterns=        design,
            anti_patterns=          anti,
            architectural_patterns= arch,
            summary=                behavioural.get("summary", structural.get("summary", "")),
        )

    @staticmethod
    def _print_summary(result: PatternDetectionResult):
        print(f"\n  Design patterns found    : {len(result.design_patterns)}")
        print(f"  Anti-patterns found      : {len(result.anti_patterns)}")
        print(f"  Architectural patterns   : {len(result.architectural_patterns)}")
        if result.summary:
            print(f"\n  Summary: {result.summary}\n")
        if result.has_anti_patterns:
            print("  Anti-patterns to address:")
            for p in result.anti_patterns:
                print(f"    [{p.confidence:6}] {p.pattern_name} @ {p.location}")
                print(f"             → {p.suggestion}")