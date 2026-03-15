import json
import os
import time
import random
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class FunctionSummarizer:
    """
    Summarizes all functions from an analyzer result using an LLM.
    Drop-in for the batch_llm_function_summary.py pipeline.
    """

    def __init__(self, batch_size: int = 10, retries: int = 3, base_delay: float = 2.0):
        self.batch_size = batch_size
        self.retries = retries
        self.base_delay = base_delay

        raw_headers = os.getenv("LLM_DEFAULT_HEADERS", "{}")
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-5.1"),
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
            default_headers=json.loads(raw_headers),
            temperature=0,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def summarize(self, analysis_result, output_path: str | Path) -> dict:
        """
        Summarize all functions in `analysis_result` and write to `output_path`.

        Args:
            analysis_result : object returned by CodeAnalyzer.analyze()
            output_path     : where to write function_llm_summaries.json

        Returns:
            dict  { function_name: { purpose, inputs, outputs, notes } }
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        contexts = [self._build_context(f) for f in analysis_result.all_functions]
        summaries = {}
        failed_batches = []

        for i in range(0, len(contexts), self.batch_size):
            batch = contexts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            print(f"  Summarizing batch {batch_num} ({len(batch)} functions)...")

            result = self._call_llm_with_retry(batch)
            summaries.update(result)

            if all(str(v).startswith("ERROR:") for v in result.values()):
                failed_batches.append(batch_num)

            # Checkpoint after every batch — don't lose progress
            with open(output_path, "w") as f:
                json.dump(summaries, f, indent=2)

        if failed_batches:
            print(f"  ⚠️  Batches that fully failed: {failed_batches}")

        print(f" {len(summaries)} function summaries → {output_path}")
        return summaries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(self, func) -> dict:
        return {
            "name":      func.name,
            "file":      getattr(func, "file_path", "unknown"),
            "class":     getattr(func, "class_name", None),
            "signature": getattr(func, "signature", ""),
            "docstring": getattr(func, "docstring", ""),
            "source":    (
                getattr(func, "source_code", "")
                or getattr(func, "source", "")
                or getattr(func, "body", "")
            ),
        }

    def _build_prompt(self, batch_contexts: list[dict]) -> str:
        functions_text = ""
        for ctx in batch_contexts:
            header = f"### {ctx['name']}"
            if ctx["class"]:
                header += f" (method of {ctx['class']})"
            header += f" — {ctx['file']}"
            functions_text += (
                f"{header}\n"
                f"Signature : {ctx['signature']}\n"
                f"Docstring : {ctx['docstring'] or 'None'}\n"
                f"Source    :\n```python\n{ctx['source'] or '(not available)'}\n```\n\n"
            )
        return functions_text

    def _call_llm_with_retry(self, batch_contexts: list[dict]) -> dict:
        messages = [
            SystemMessage(content=(
                "You are a senior Python developer doing a codebase audit. "
                "For each function, return a JSON object with these keys:\n"
                "  'purpose' : one sentence on what it does\n"
                "  'inputs'  : key parameters and their meaning\n"
                "  'outputs' : what it returns\n"
                "  'notes'   : side-effects, raises, or important caveats\n\n"
                "Respond ONLY with a valid JSON object: "
                "{function_name: {purpose, inputs, outputs, notes}}. "
                "No markdown, no extra text."
            )),
            HumanMessage(content=f"Summarize these functions:\n\n{self._build_prompt(batch_contexts)}")
        ]

        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.llm.invoke(messages)
                try:
                    return json.loads(response.content)
                except json.JSONDecodeError:
                    print("  Warning: JSON parse failed, storing raw output.")
                    return {ctx["name"]: response.content for ctx in batch_contexts}

            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    print(f"  Attempt {attempt} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    print(f"  All {self.retries} attempts failed.")

        return {ctx["name"]: f"ERROR: {last_error}" for ctx in batch_contexts}