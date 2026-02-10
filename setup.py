from src.ingest import CodeIngestor
from src.analyzers import CodeAnalyzer
from src.diagram_generators import DiagramGenerator
ingestor = CodeIngestor()

ingestion = ingestor.ingest("https://github.com/ysz/recursive-llm.git")
# result = ingestor.ingest("/Users/purverma/Documents/ArchitectMapper/codemap/src/analyzers")
# result = ingestor.ingest("script.py")
analyzer = CodeAnalyzer()
result = analyzer.analyze(ingestion)

# Rich analysis results
print(f"Classes: {len(result.all_classes)}")
print(f"Functions: {len(result.all_functions)}")
print(f"Dependencies: {len(result.dependencies)}")

# Generate full report
report = analyzer.generate_full_report(ingestion)

generator = DiagramGenerator()
diagrams = generator.generate_all(result)
diagrams.save_all("./diagrams")