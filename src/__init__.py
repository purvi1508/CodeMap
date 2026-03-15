# Ingest GitHub repo
#         ↓
# CodeAnalyzer  →  function_summary.json          (no LLM)
#         ↓
# DiagramGenerator  →  diagrams/*.mmd             (no LLM — call_graph, class, dependency)
#         ↓
# FunctionSummarizer  →  function_llm_summaries.json   (~8 LLM calls for 79 functions)
#         ↓
# PatternDetector  →  pattern_detection.json           (2 LLM calls)
#         ↓
# OpenAIAnalyzer  →  architecture/                     (3 LLM calls)
#                      ├── architecture_plan.json
#                      ├── arch_c4_context.mmd
#                      ├── arch_c4_container.mmd
#                      ├── arch_c4_component.mmd
#                      ├── arch_deployment.mmd
#                      └── arch_data_flow.mmd