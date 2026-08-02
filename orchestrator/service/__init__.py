"""Service-layer projections for the product surface.

This package assembles read models from the deterministic orchestrator
artifacts.  The first and (for now) only projection is ``CaseView`` — a
single versioned document that the frontend consumes.

Import directly from ``orchestrator.service.caseview`` to avoid eager
package-level imports that could create cycles.
"""

from orchestrator.service.caseview import CaseView, build_case_view

__all__ = ["CaseView", "build_case_view"]
