"""
Data models for code analysis results.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Set, Any
from enum import Enum


class Visibility(Enum):
    """Visibility/access level of class members."""
    PUBLIC = "public"
    PROTECTED = "protected"  # _method
    PRIVATE = "private"      # __method


class NodeType(Enum):
    """Types of code nodes."""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    DECORATOR = "decorator"


@dataclass
class Parameter:
    """Function/method parameter."""
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    is_keyword_only: bool = False
    is_positional_only: bool = False


@dataclass
class FunctionInfo:
    """Information about a function or method."""
    name: str
    node_type: NodeType  # FUNCTION or METHOD
    parameters: List[Parameter] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_number: int = 0
    end_line_number: int = 0
    is_async: bool = False
    is_property: bool = False
    visibility: Visibility = Visibility.PUBLIC
    calls: List[str] = field(default_factory=list)  # Functions called within
    complexity: int = 1  # Cyclomatic complexity
    
    def __post_init__(self):
        """Determine visibility from name."""
        if self.name.startswith('__') and not self.name.endswith('__'):
            self.visibility = Visibility.PRIVATE
        elif self.name.startswith('_'):
            self.visibility = Visibility.PROTECTED


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    base_classes: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_number: int = 0
    end_line_number: int = 0
    is_abstract: bool = False
    is_dataclass: bool = False
    inner_classes: List['ClassInfo'] = field(default_factory=list)
    
    def get_public_methods(self) -> List[FunctionInfo]:
        """Get all public methods."""
        return [m for m in self.methods if m.visibility == Visibility.PUBLIC]
    
    def get_constructor(self) -> Optional[FunctionInfo]:
        """Get __init__ method if exists."""
        return next((m for m in self.methods if m.name == '__init__'), None)


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    names: List[str] = field(default_factory=list)  # specific imports
    alias: Optional[str] = None
    is_from_import: bool = False
    line_number: int = 0


@dataclass
class ModuleInfo:
    """Information about a Python module (file)."""
    name: str
    file_path: Path
    docstring: Optional[str] = None
    imports: List[ImportInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    global_variables: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)
    total_lines: int = 0
    
    def get_all_functions(self) -> List[FunctionInfo]:
        """Get all functions including class methods."""
        all_funcs = self.functions.copy()
        for cls in self.classes:
            all_funcs.extend(cls.methods)
        return all_funcs
    
    def get_dependencies(self) -> Set[str]:
        """Get set of all imported modules."""
        return {imp.module for imp in self.imports}


@dataclass
class CallGraphEdge:
    """An edge in the call graph."""
    caller: str  # Function that makes the call
    callee: str  # Function being called
    call_count: int = 1
    line_number: int = 0


@dataclass
class DependencyEdge:
    """A dependency between modules."""
    source: str  # Source module
    target: str  # Target module (imported)
    import_type: str = "import"  # "import" or "from_import"
    names: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Complete analysis result for a codebase."""
    modules: Dict[str, ModuleInfo] = field(default_factory=dict)
    call_graph: List[CallGraphEdge] = field(default_factory=list)
    dependencies: List[DependencyEdge] = field(default_factory=list)
    all_classes: List[ClassInfo] = field(default_factory=list)
    all_functions: List[FunctionInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_module(self, path: Path) -> Optional[ModuleInfo]:
        """Get module info by file path."""
        return self.modules.get(str(path))
    
    def get_class_by_name(self, name: str) -> Optional[ClassInfo]:
        """Find a class by name."""
        return next((cls for cls in self.all_classes if cls.name == name), None)
    
    def get_function_by_name(self, name: str) -> Optional[FunctionInfo]:
        """Find a function by name."""
        return next((func for func in self.all_functions if func.name == name), None)
    
    def get_module_dependencies(self, module_name: str) -> List[str]:
        """Get all modules that a module depends on."""
        return [dep.target for dep in self.dependencies if dep.source == module_name]
    
    def get_module_dependents(self, module_name: str) -> List[str]:
        """Get all modules that depend on a module."""
        return [dep.source for dep in self.dependencies if dep.target == module_name]


@dataclass
class APIEndpoint:
    """Information about an API endpoint."""
    path: str
    method: str  # GET, POST, etc.
    function_name: str
    decorators: List[str] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    module: str = ""
    line_number: int = 0
    
    def __str__(self):
        return f"{self.method} {self.path} -> {self.function_name}"


@dataclass
class APIAnalysisResult:
    """Analysis result specific to API frameworks."""
    framework: str  # "flask", "fastapi", "django"
    endpoints: List[APIEndpoint] = field(default_factory=list)
    base_path: Optional[str] = None
    
    def get_endpoints_by_method(self, method: str) -> List[APIEndpoint]:
        """Get all endpoints for a specific HTTP method."""
        return [ep for ep in self.endpoints if ep.method.upper() == method.upper()]
    
    def get_endpoint_count(self) -> Dict[str, int]:
        """Count endpoints by HTTP method."""
        counts = {}
        for endpoint in self.endpoints:
            method = endpoint.method.upper()
            counts[method] = counts.get(method, 0) + 1
        return counts