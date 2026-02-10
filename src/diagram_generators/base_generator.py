"""
Base diagram generator with common utilities.
"""
from abc import ABC, abstractmethod
from typing import List, Set, Optional
import re

from ..analyzers.models import (
    AnalysisResult, ClassInfo, FunctionInfo, 
    ModuleInfo, Visibility
)
from .models import DiagramConfig, DiagramOutput, DiagramFormat


class BaseDiagramGenerator(ABC):
    """Abstract base class for diagram generators."""
    
    def __init__(self, config: DiagramConfig):
        """
        Initialize the generator.
        
        Args:
            config: Diagram configuration
        """
        self.config = config
    
    @abstractmethod
    def generate(self, analysis_result: AnalysisResult) -> DiagramOutput:
        """
        Generate a diagram from analysis results.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            DiagramOutput with generated content
        """
        pass
    
    def should_include_class(self, class_info: ClassInfo) -> bool:
        """Check if a class should be included in the diagram."""
        # Check name patterns
        if not self.config.should_include(class_info.name):
            return False
        
        return True
    
    def should_include_function(self, func_info: FunctionInfo) -> bool:
        """Check if a function should be included in the diagram."""
        # Check name patterns
        if not self.config.should_include(func_info.name):
            return False
        
        # Check visibility
        if func_info.visibility == Visibility.PRIVATE and not self.config.include_private:
            return False
        
        if func_info.visibility == Visibility.PROTECTED and not self.config.include_protected:
            return False
        
        # Check magic methods
        if func_info.name.startswith('__') and func_info.name.endswith('__'):
            if not self.config.include_magic_methods:
                return False
        
        return True
    
    def should_include_method(self, method_info: FunctionInfo) -> bool:
        """Check if a method should be included (alias for function)."""
        return self.should_include_function(method_info)
    
    def sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in diagrams.
        
        Args:
            name: Raw name
            
        Returns:
            Sanitized name
        """
        # Remove special characters that might break diagram syntax
        return name.replace('<', '').replace('>', '').replace('{', '').replace('}', '')
    
    def format_type(self, type_str: Optional[str]) -> str:
        """
        Format a type annotation for display.
        
        Args:
            type_str: Type string
            
        Returns:
            Formatted type string
        """
        if not type_str:
            return ""
        
        # Simplify complex types
        type_str = type_str.replace('typing.', '')
        
        return type_str
    
    def format_parameters(self, func_info: FunctionInfo) -> str:
        """
        Format function parameters for display.
        
        Args:
            func_info: Function information
            
        Returns:
            Formatted parameter string
        """
        if not self.config.show_parameters:
            return ""
        
        params = []
        for param in func_info.parameters:
            if param.name in ['self', 'cls']:
                continue
            
            param_str = param.name
            
            if param.type_annotation and self.config.show_return_types:
                param_str += f": {self.format_type(param.type_annotation)}"
            
            if param.default_value:
                param_str += f" = {param.default_value}"
            
            params.append(param_str)
        
        return ", ".join(params)
    
    def get_visibility_symbol(self, visibility: Visibility) -> str:
        """
        Get UML visibility symbol.
        
        Args:
            visibility: Visibility enum
            
        Returns:
            UML symbol (+, -, #)
        """
        symbols = {
            Visibility.PUBLIC: '+',
            Visibility.PROTECTED: '#',
            Visibility.PRIVATE: '-'
        }
        return symbols.get(visibility, '+')
    
    def filter_classes(self, classes: List[ClassInfo]) -> List[ClassInfo]:
        """
        Filter classes based on configuration.
        
        Args:
            classes: List of classes
            
        Returns:
            Filtered list
        """
        filtered = [c for c in classes if self.should_include_class(c)]
        
        # Apply max limit if set
        if self.config.max_classes and len(filtered) > self.config.max_classes:
            filtered = filtered[:self.config.max_classes]
        
        return filtered
    
    def filter_functions(self, functions: List[FunctionInfo]) -> List[FunctionInfo]:
        """
        Filter functions based on configuration.
        
        Args:
            functions: List of functions
            
        Returns:
            Filtered list
        """
        filtered = [f for f in functions if self.should_include_function(f)]
        
        # Apply max limit if set
        if self.config.max_functions and len(filtered) > self.config.max_functions:
            filtered = filtered[:self.config.max_functions]
        
        return filtered
    
    def escape_string(self, text: str) -> str:
        """
        Escape special characters in strings.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        if not text:
            return ""
        
        # Escape quotes and backslashes
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace("'", "\\'")
        
        return text
    
    def truncate_text(self, text: str, max_length: int = 50) -> str:
        """
        Truncate text to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            
        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."
    
    def indent(self, text: str, spaces: int = 2) -> str:
        """
        Indent text by a number of spaces.
        
        Args:
            text: Text to indent
            spaces: Number of spaces
            
        Returns:
            Indented text
        """
        indent_str = " " * spaces
        return "\n".join(indent_str + line for line in text.split("\n"))
    
    def wrap_in_block(self, content: str, block_type: str = "") -> str:
        """
        Wrap content in a code block.
        
        Args:
            content: Content to wrap
            block_type: Block type (for markdown)
            
        Returns:
            Wrapped content
        """
        return f"```{block_type}\n{content}\n```"