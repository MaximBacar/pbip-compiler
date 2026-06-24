"""Report compilation — PBIR/PBIR-legacy → legacy Report/Layout + resources."""

from __future__ import annotations

from .layout import ReportLayoutLoader
from .pbir import PbirCompiler
from .resources import StaticResourceCollector

__all__ = ["ReportLayoutLoader", "PbirCompiler", "StaticResourceCollector"]
