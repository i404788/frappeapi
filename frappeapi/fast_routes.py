"""
Starlette‑style path routing for **FrappeAPI**
==============================================

🎯 Purpose
----------
• Enable decorators like `@app.get("/items/{code}")` next to the existing
  dotted‑path system.
• Use routes registered in the FrappeAPI app instance without duplication.
• Leave every Frappe lifecycle guarantee intact (DB, auth, error handling).

🔥 How it works
--------------
1. Each FrappeAPI instance registers routes in its self.router.routes collection.
2. At import time we monkey‑patch **`frappe.api.handle`**:
   • For every `/api/**` request we check against the registered routes.
   • On a match, we extract path parameters and call the corresponding handler.
   • If nothing matches we fall back to the original `frappe.api.handle`.

This file is *pure Python*; no Frappe changes on disk are required.
"""

from __future__ import annotations

import types
from enum import Enum
from typing import Any, Callable, List, Optional, Type, Union

import frappe
from fastapi.datastructures import Default
from starlette.routing import Match, Route
from werkzeug.wrappers import Response as WerkzeugResponse

from frappeapi.responses import JSONResponse

# Export the HTTP method decorators
__all__ = [
	"GET",
	"POST",
	"PUT",
	"DELETE",
	"PATCH",
	"OPTIONS",
	"HEAD",
	"register_app",
]

# Keep track of all FrappeAPI instances
_FRAPPEAPI_INSTANCES = []


def register_app(app):
	"""Register a FrappeAPI instance to be considered for routing."""
	if app not in _FRAPPEAPI_INSTANCES:
		_FRAPPEAPI_INSTANCES.append(app)


# HTTP method decorators (used by FrappeAPI._dual)
# These are simple pass-through functions that delegate to the router
def _factory(methods: List[str]) -> Callable:
	def decorator(
		path: str,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		allow_guest: bool = False,
		xss_safe: bool = False,
		fastapi_path_format: bool = False,
	) -> Callable[[Callable], Callable]:
		def register(func: Callable) -> Callable:
			# This is just a pass-through - the actual registration happens in applications.py
			# via the FrappeAPI._dual method
			return func

		return register

	return decorator


# Create the HTTP method decorators
GET = _factory(["GET"])
POST = _factory(["POST"])
PUT = _factory(["PUT"])
DELETE = _factory(["DELETE"])
PATCH = _factory(["PATCH"])
OPTIONS = _factory(["OPTIONS"])
HEAD = _factory(["HEAD"])


def _install_patch() -> None:
	"""Install the patch to frappe.api.handle once per process."""
	if getattr(frappe, "_fastapi_path_patch_done", False):
		return

	orig_handle = frappe.api.handle

	def patched_handle() -> types.ModuleType | dict:
		# Get the original path
		original_path = frappe.local.request.path
		path = original_path

		# Only strip /api/ prefix if it's not a dotted path route (/api/method/)
		if path.startswith("/api/") and not path.startswith("/api/method/"):
			path = path[4:]  # Remove /api prefix

		# Check against all registered routes in all FrappeAPI instances
		for app in _FRAPPEAPI_INSTANCES:
			# Skip app instances that don't have a router or routes
			if not hasattr(app, "router") or not hasattr(app.router, "routes"):
				continue

			for api_route in app.router.routes:
				# Skip routes that aren't meant for FastAPI-style paths
				if not getattr(api_route, "fastapi_path_format", False) or not getattr(api_route, "fastapi_path", None):
					continue

				# Create a scope for Starlette routing
				scope = {
					"type": "http",
					"path": path,
					"root_path": "",
					"method": frappe.local.request.method.upper(),
				}

				# Create a temporary Starlette route for matching
				# Use the fastapi_path directly to ensure proper matching
				route_path = api_route.fastapi_path
				starlette_route = Route(route_path, endpoint=api_route.endpoint, methods=[m for m in api_route.methods])

				match, child = starlette_route.matches(scope)
				if match == Match.FULL:
					# Extract path parameters
					path_params = child.get("path_params", {})

					try:
						# Set path_params directly on the request object
						frappe.local.request.path_params = path_params

						# Use the APIRoute to handle the request
						response = api_route.handle_request()
						return response
					except Exception:
						raise  # Let Frappe handle the exception

		# No FastAPI-style route matched, fall back to original handler
		return orig_handle()

	frappe.api.handle = patched_handle
	frappe._fastapi_path_patch_done = True


# Install the patch when this module is imported
_install_patch()
