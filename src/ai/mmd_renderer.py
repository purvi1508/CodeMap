# src/ai/mmd_renderer.py

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class MmdRenderer:
    """
    Converts .mmd files to PNG using @mermaid-js/mermaid-cli (mmdc).

    On failure, feeds the broken .mmd + the exact mmdc error to an LLM
    which rewrites the file. Retries up to MAX_RETRIES times per file.
    The original .mmd is always preserved as <name>.mmd.bak before any
    LLM rewrite so you can diff what changed.

    Install mmdc once:
        npm install -g @mermaid-js/mermaid-cli

    Usage:
        renderer = MmdRenderer(output_format="png", width=2400)
        renderer.render_dir("codemap/architecture")
        renderer.render_dir("diagrams")
    """

    MAX_RETRIES = 3

    _SYSTEM_FIX = """
You are a Mermaid diagram expert.
You will receive a broken Mermaid diagram source and the exact error
produced by the Mermaid CLI (mmdc) when it tried to render it.

Fix the diagram so it renders correctly. Rules:
- Keep the diagram's intent and content identical — only fix syntax
- No () inside [] node labels              e.g. [Label (Ext)] → [Label]
- No `break` statements
- No invalid node IDs (spaces → underscores, no special chars in IDs)
- subgraph labels must not contain special characters in their ID part
  e.g.  subgraph EXT [External Systems]  is fine
        subgraph EXT(External Systems)   is NOT fine
- Arrow labels must be quoted if they contain colons or special chars
  e.g.  A -->|"HTTP: JSON"| B
- sequenceDiagram participants must be declared before use
- C4Context / C4Container / C4Component must use correct C4 Mermaid syntax
- Do NOT add markdown fences (```mermaid) — return raw Mermaid source only

Respond ONLY with the corrected Mermaid source. No explanation, no markdown.
""".strip()

    def __init__(
        self,
        output_format: str = "png",
        width:         int  = 2400,
        background:    str  = "white",
        retries:       int  = MAX_RETRIES,
    ):
        self.output_format = output_format
        self.width         = width
        self.background    = background
        self.retries       = retries

        raw_headers = os.getenv("LLM_DEFAULT_HEADERS", "{}")
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-5.1"),
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            default_headers=json.loads(raw_headers),
            temperature=0,
        )

        self._check_mmdc()

    # ── public ─────────────────────────────────────────────────────────

    def render_dir(self, diagrams_dir: str | Path) -> dict[str, list[Path]]:
        """
        Render all .mmd files in a directory.

        Returns:
            {
              "success": [Path, ...],   # files that rendered cleanly
              "healed":  [Path, ...],   # files fixed by LLM then rendered
              "failed":  [Path, ...],   # files that failed all retries
            }
        """
        d = Path(diagrams_dir)
        if not d.exists():
            print(f"  [MmdRenderer] Directory not found: {d}")
            return {"success": [], "healed": [], "failed": []}

        results: dict[str, list[Path]] = {"success": [], "healed": [], "failed": []}

        for mmd_file in sorted(d.glob("*.mmd")):
            status, out = self.render_file(mmd_file)
            results[status].append(out or mmd_file)

        total = sum(len(v) for v in results.values())
        print(
            f"\n  [MmdRenderer] {d.name}/ — "
            f"{len(results['success'])} clean, "
            f"{len(results['healed'])} healed, "
            f"{len(results['failed'])} failed  "
            f"(total {total})"
        )
        return results

    def render_file(self, mmd_file: str | Path) -> tuple[str, Path | None]:
        """
        Render one .mmd file with up to self.retries LLM-assisted fix attempts.

        Returns:
            ("success", output_path)  — rendered cleanly on first try
            ("healed",  output_path)  — rendered after LLM fix(es)
            ("failed",  None)         — all retries exhausted
        """
        mmd_file = Path(mmd_file)
        out_file = mmd_file.with_suffix(f".{self.output_format}")
        healed   = False

        print(f"\n  [MmdRenderer] ── {mmd_file.name}")

        for attempt in range(1, self.retries + 1):
            error = self._run_mmdc(mmd_file, out_file)

            if error is None:
                tag = "✓ clean" if not healed else "✓ healed"
                print(f"    attempt {attempt}: {tag} → {out_file.name}")
                return ("healed" if healed else "success"), out_file

            print(f"    attempt {attempt} failed: {error[:120].strip()}")

            if attempt < self.retries:
                print(f"    → asking LLM to fix (attempt {attempt}/{self.retries - 1})...")
                self._llm_fix(mmd_file, error, attempt)
                healed = True
            else:
                print(f"    ✗ all {self.retries} attempts failed — {mmd_file.name} unchanged")

        return "failed", None

    # ── mmdc runner ────────────────────────────────────────────────────

    def _run_mmdc(self, mmd_file: Path, out_file: Path) -> str | None:
        """
        Run mmdc. Returns None on success, or the error string on failure.
        """
        cmd = [
            "mmdc",
            "-i", str(mmd_file),
            "-o", str(out_file),
            "--width",           str(self.width),
            "--backgroundColor", self.background,
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and out_file.exists():
                return None

            # Collect the most informative error available
            error = (result.stderr or result.stdout or "unknown error").strip()
            return error or f"mmdc exited with code {result.returncode}"

        except subprocess.TimeoutExpired:
            return "mmdc timed out after 60s"
        except Exception as e:
            return str(e)

    # ── LLM fixer ──────────────────────────────────────────────────────

    def _llm_fix(self, mmd_file: Path, error: str, attempt: int):
        """
        Ask the LLM to rewrite mmd_file given the mmdc error.
        Backs up the original before overwriting.
        """
        original_source = mmd_file.read_text(encoding="utf-8")

        # Keep a backup of the very first version on attempt 1
        bak = mmd_file.with_suffix(".mmd.bak")
        if attempt == 1 and not bak.exists():
            bak.write_text(original_source, encoding="utf-8")
            print(f"    backed up original → {bak.name}")

        user_prompt = (
            f"The following Mermaid diagram failed to render.\n\n"
            f"## Error from mmdc\n```\n{error}\n```\n\n"
            f"## Broken Mermaid source\n```\n{original_source}\n```\n\n"
            f"Return ONLY the corrected Mermaid source."
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=self._SYSTEM_FIX),
                HumanMessage(content=user_prompt),
            ])

            fixed = self._clean_llm_response(response.content)

            if fixed and fixed != original_source:
                mmd_file.write_text(fixed, encoding="utf-8")
                print(f"    LLM rewrote {mmd_file.name} ({len(original_source)}→{len(fixed)} chars)")
            else:
                print(f"    LLM returned identical source — skipping overwrite")

        except Exception as e:
            print(f"    LLM fix failed: {e}")

    @staticmethod
    def _clean_llm_response(content: str) -> str:
        """Strip markdown fences the LLM might add despite instructions."""
        content = content.strip()
        # Remove ```mermaid ... ``` or ``` ... ```
        content = re.sub(r"^```(?:mermaid)?\s*\n?", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\n?```\s*$", "", content)
        return content.strip()

    # ── sanity check ───────────────────────────────────────────────────

    @staticmethod
    def _check_mmdc():
        if not shutil.which("mmdc"):
            raise EnvironmentError(
                "mmdc not found.\n"
                "Install with:  npm install -g @mermaid-js/mermaid-cli"
            )