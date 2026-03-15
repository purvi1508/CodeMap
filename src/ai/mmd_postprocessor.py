# src/ai/mmd_postprocessor.py

import re
from pathlib import Path


class MmdPostProcessor:
    """
    Cleans up generated .mmd files in-place.

    Rules applied
    ─────────────
    1. Remove any `break` statements (invalid in most Mermaid renderers)
    2. Strip parenthetical suffixes from node/subgraph labels inside brackets
       e.g.  [External LLM Provider \n(Ext)]  →  [External LLM Provider]
             [API Gateway\n(Ext)]              →  [API Gateway]
    3. Collapse any double-blank lines left after removals
    """

    def process_dir(self, diagrams_dir: str | Path) -> list[Path]:
        """
        Process all .mmd files in `diagrams_dir` in-place.
        Returns list of files that were modified.
        """
        d = Path(diagrams_dir)
        if not d.exists():
            print(f"  [MmdPostProcessor] Directory not found: {d}")
            return []

        modified = []
        for mmd_file in sorted(d.glob("*.mmd")):
            original = mmd_file.read_text(encoding="utf-8")
            cleaned  = self.process_text(original)
            if cleaned != original:
                mmd_file.write_text(cleaned, encoding="utf-8")
                modified.append(mmd_file)
                print(f"  [MmdPostProcessor] Cleaned {mmd_file.name}")
            else:
                print(f"  [MmdPostProcessor] No changes {mmd_file.name}")

        return modified

    def process_text(self, text: str) -> str:
        text = self._remove_break(text)
        text = self._remove_parens_in_brackets(text)
        text = self._collapse_blank_lines(text)
        return text

    # ── rules ─────────────────────────────────────────────────────────

    @staticmethod
    def _remove_break(text: str) -> str:
        """Remove lines that contain only `break` (optionally indented)."""
        lines = text.splitlines()
        cleaned = [ln for ln in lines if ln.strip() != "break"]
        return "\n".join(cleaned)

    @staticmethod
    def _remove_parens_in_brackets(text: str) -> str:
        """
        Inside [...] node labels and subgraph [...] labels, strip any
        parenthetical expression — including those after a \\n literal.

        Examples:
          [External LLM Provider \n(Ext)]  →  [External LLM Provider]
          [API Gateway\n(Ext)]             →  [API Gateway]
          [Worker Service (internal)]      →  [Worker Service]
          ["Some Label (Ext)"]             →  ["Some Label"]
        """
        def strip_parens(m: re.Match) -> str:
            content = m.group(1)
            # Remove \n(anything) or just (anything) at the end
            content = re.sub(r'\\n\s*\([^)]*\)', '', content)
            content = re.sub(r'\s*\([^)]*\)',    '', content)
            content = content.strip()
            return f"[{content}]"

        # Match [...] but not [[...]] (Mermaid wiki-links) or [(...)] (cylinders)
        return re.sub(r'\[(?!\[)([^\[\]]+)\]', strip_parens, text)

    @staticmethod
    def _collapse_blank_lines(text: str) -> str:
        """Replace 3+ consecutive blank lines with a single blank line."""
        return re.sub(r'\n{3,}', '\n\n', text)