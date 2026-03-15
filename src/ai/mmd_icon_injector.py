import json
import re
from pathlib import Path


class MmdIconInjector:
    """
    Injects icon <img> tags into Mermaid node labels using icon_link.json.

    How it works
    ─────────────
    1. Loads icon_link.json  →  { "Redis": ["url1", "url2"], ... }
    2. Builds a normalised lookup: "redis" → "url1"
    3. For every .mmd file, scans node labels inside [...]
       and replaces matching labels with an HTML img + label
    4. Prepends  %%{init: {'securityLevel':'loose'}}%%
       so Mermaid renders the HTML (required for <img> in labels)

    Matching is normalised (lowercase, strip spaces/underscores/hyphens)
    so "Load Balancer", "load_balancer", "loadbalancer" all match "LoadBalancer".

    Usage:
        injector = MmdIconInjector("codemap/icon_link.json")
        injector.process_dir("codemap/architecture")
        injector.process_file("codemap/diagrams/class_0.mmd")
    """

    IMG_SIZE = 40          # px — icon size inside node label
    INIT_DIRECTIVE = "%%{init: {'securityLevel': 'loose'}}%%\n"

    def __init__(self, icon_json_path: str | Path):
        self.icon_map = self._load_icons(icon_json_path)

    # ── public ─────────────────────────────────────────────────────────

    def process_dir(self, diagrams_dir: str | Path) -> list[Path]:
        """Process all .mmd files in a directory in-place."""
        d = Path(diagrams_dir)
        if not d.exists():
            print(f"  [MmdIconInjector] Directory not found: {d}")
            return []

        modified = []
        for mmd_file in sorted(d.glob("*.mmd")):
            if self.process_file(mmd_file):
                modified.append(mmd_file)

        print(f"  [MmdIconInjector] {len(modified)} file(s) updated in {d.name}")
        return modified

    def process_file(self, mmd_file: str | Path) -> bool:
        """Process a single .mmd file in-place. Returns True if changed."""
        mmd_file = Path(mmd_file)
        original = mmd_file.read_text(encoding="utf-8")
        updated  = self.process_text(original)
        if updated != original:
            mmd_file.write_text(updated, encoding="utf-8")
            print(f"  [MmdIconInjector] Icons injected → {mmd_file.name}")
            return True
        print(f"  [MmdIconInjector] No matches      → {mmd_file.name}")
        return False

    def process_text(self, text: str) -> str:
        if not self.icon_map:
            return text

        # Add init directive only if not already present
        if "securityLevel" not in text:
            text = self.INIT_DIRECTIVE + text

        # Replace matching node labels   NodeId[Label]  →  NodeId["<img...><br/>Label"]
        text = re.sub(
            r'(\w[\w\s]*?)\[([^\[\]]+?)\]',
            self._replace_label,
            text,
        )
        return text

    # ── private ────────────────────────────────────────────────────────

    def _replace_label(self, m: re.Match) -> str:
        node_id = m.group(1)
        label   = m.group(2).strip()

        # Don't touch subgraph headers or already-injected labels
        if "<img" in label or label.startswith('"'):
            return m.group(0)

        icon_url = self._find_icon(label) or self._find_icon(node_id)
        if not icon_url:
            return m.group(0)

        # Clean label text (remove any \n literals from prior post-processing)
        clean_label = re.sub(r'\\n', ' ', label).strip()

        html = (
            f'"<img src=\'{icon_url}\' '
            f'width=\'{self.IMG_SIZE}\' height=\'{self.IMG_SIZE}\' '
            f'style=\'display:block;margin:auto;\'/>'
            f'<br/>{clean_label}"'
        )
        return f"{node_id}[{html}]"

    def _find_icon(self, text: str) -> str | None:
        """Return the first icon URL whose key fuzzy-matches `text`."""
        key = self._normalise(text)
        for icon_key, urls in self.icon_map.items():
            if self._normalise(icon_key) in key or key in self._normalise(icon_key):
                return urls[0] if urls else None
        return None

    @staticmethod
    def _normalise(s: str) -> str:
        return re.sub(r'[\s_\-]', '', s).lower()

    @staticmethod
    def _load_icons(path: str | Path) -> dict:
        try:
            with open(path) as f:
                data = json.load(f)
            print(f"  [MmdIconInjector] Loaded {len(data)} icon keys from {Path(path).name}")
            return data
        except Exception as e:
            print(f"  [MmdIconInjector] Could not load icons: {e}")
            return {}