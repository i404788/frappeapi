"""
Starlette‑style path routing for **FrappeAPI**
==============================================

🎯 Purpose
----------
• Enable decorators like `@app.get("/items/{code}")` next to the existing
  dotted‑path system.
• Keep everything *per‑FrappeAPI instance* but patch request dispatch once.
• Leave every Frappe lifecycle guarantee intact (DB, auth, error handling).

🔥 How it works
--------------
1. Each decorator registers a `starlette.routing.Route` (regex compiled by
   `compile_path`) into a local list.
2. At import time we monkey‑patch **`frappe.api.handle`**:
   • For every `/api/**` request we iterate over those routes and call
     `route.matches(scope)` – the same logic FastAPI uses.
   • On `Match.FULL` we run the endpoint with extracted params, set
     `frappe.local.response["message"]`, and return.
   • If nothing matches we fall back to the original `frappe.api.handle`.

This file is *pure Python*; no Frappe changes on disk are required.
"""

from __future__ import annotations

import types
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import frappe
from fastapi.datastructures import Default
from starlette.routing import Match, Route
from werkzeug.wrappers import Response as WerkzeugResponse

from frappeapi.responses import JSONResponse
from frappeapi.routing import APIRoute

__all__ = [
	"GET",
	"POST",
	"PUT",
	"DELETE",
	"PATCH",
	"OPTIONS",
	"HEAD",
	"add_route",
]

# --------------------------------------------------------------------------- #
# Internal registry (per‑process; each FrappeAPI instance adds to it)
# --------------------------------------------------------------------------- #

# Store both Starlette routes (for path matching) and APIRoutes (for handling)
_STARLETTE_ROUTES: List[Tuple[Route, APIRoute]] = []


def add_route(
	path: str,
	methods: list[str],
	endpoint: Callable,
	*,
	allow_guest: bool = False,
	response_model: Any = Default(None),
	status_code: Optional[int] = None,
	description: Optional[str] = None,
	tags: Optional[List] = None,
	summary: Optional[str] = None,
	include_in_schema: bool = True,
	response_class: Type[WerkzeugResponse] = Default(JSONResponse),
	exception_handlers: Optional[Dict[Type[Exception], Callable]] = None,
) -> None:
	"""Register a Starlette ``Route`` and corresponding APIRoute, and whitelist the endpoint."""
	# Ensure the function is whitelisted in Frappe
	if not hasattr(endpoint, "_whitelisted"):
		# Apply frappe.whitelist with appropriate methods
		endpoint = frappe.whitelist(methods=methods, allow_guest=allow_guest)(endpoint)

	# Also add to Frappe's whitelist registry to be sure
	# Check if frappe.whitelisted exists and is a list before appending
	if hasattr(frappe, "whitelisted") and isinstance(frappe.whitelisted, list):
		if endpoint not in frappe.whitelisted:
			frappe.whitelisted.append(endpoint)

	# Check if guest_methods exists and is a list before appending
	if allow_guest and hasattr(frappe, "guest_methods") and isinstance(frappe.guest_methods, list):
		if endpoint not in frappe.guest_methods:
			frappe.guest_methods.append(endpoint)

	# Create both Route objects:
	# 1. A Starlette Route for path matching
	starlette_route = Route(path, endpoint=endpoint, methods=[m.upper() for m in methods])

	# 2. An APIRoute for proper request handling with same parameters as would be used
	# in traditional dotted-path routing
	api_route = APIRoute(
		endpoint,
		methods=methods,  # Pass methods explicitly
		response_model=response_model,
		status_code=status_code,
		description=description,
		tags=tags,
		summary=summary,
		include_in_schema=include_in_schema,
		response_class=response_class,
		exception_handlers=exception_handlers or {},
	)

	# Store both routes together
	_STARLETTE_ROUTES.append((starlette_route, api_route))


# --------------------------------------------------------------------------- #
# Public decorators (mirror FastAPI names)
# --------------------------------------------------------------------------- #


def _factory(methods: list[str]) -> Callable:
	def decorator(
		path: str,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		allow_guest: bool = False,
		xss_safe: bool = False,
	) -> Callable[[Callable], Callable]:
		def register(func: Callable) -> Callable:
			# Get allow_guest setting from the function if it's already been decorated
			# or use the one provided in the decorator
			func_allow_guest = getattr(func, "allow_guest", allow_guest)

			# Pass through all the APIRoute parameters
			add_route(
				path,
				methods,
				func,
				allow_guest=func_allow_guest,
				response_model=response_model,
				status_code=status_code,
				description=description,
				tags=tags,
				summary=summary,
				include_in_schema=include_in_schema,
				response_class=response_class,
			)
			return func

		return register

	return decorator


GET = _factory(["GET"])
POST = _factory(["POST"])
PUT = _factory(["PUT"])
DELETE = _factory(["DELETE"])
PATCH = _factory(["PATCH"])
OPTIONS = _factory(["OPTIONS"])
HEAD = _factory(["HEAD"])

# --------------------------------------------------------------------------- #
# Patch frappe.api.handle (once per process)
# --------------------------------------------------------------------------- #


def _install_patch() -> None:
	if getattr(frappe, "_fastapi_patch_done", False):
		return

	orig_handle = frappe.api.handle

	def patched_handle() -> types.ModuleType | dict:
		# Get the original path
		original_path = frappe.local.request.path
		path = original_path

		# Only strip /api/ prefix if it's not a dotted path route (/api/method/)
		if path.startswith("/api/") and not path.startswith("/api/method/"):
			path = path[4:]  # Remove /api prefix

		# Build a minimal ASGI‑style scope
		scope = {
			"type": "http",
			"path": path,  # Use modified path
			"root_path": "",
			"method": frappe.local.request.method.upper(),
		}

		for starlette_route, api_route in _STARLETTE_ROUTES:
			match, child = starlette_route.matches(scope)
			if match is Match.FULL:
				# Extract path parameters
				path_params = child.get("path_params", {})

				try:
					# Store path parameters where request handlers can access them
					# This is a backup method; APIRoute.handle_request should
					# extract query params from the request, but it doesn't hurt to add them here too
					if path_params:
						frappe.form_dict = frappe.form_dict or {}  # Initialize if None
						# Copy to both form_dict (legacy) and local.form_dict (current)
						frappe.form_dict.update(path_params)
						if hasattr(frappe, "local") and hasattr(frappe.local, "form_dict"):
							frappe.local.form_dict.update(path_params)

					# Make sure frappe.local.response exists for consistent handling
					if not hasattr(frappe, "local") or not hasattr(frappe.local, "response"):
						frappe.local.response = {"message": None, "exception": None}

					# CRITICAL: Use APIRoute.handle_request() for proper request processing
					# The function doesn't expect any arguments according to its signature
					response = api_route.handle_request()

					# For FastAPI routes, we want to keep the direct response format without
					# the message wrapper, so we don't need to modify the response.
					# APIRoute.handle_request() will return the correct format directly.
					return response
				except Exception:
					raise  # Let Frappe do rollback & JSON‑ify error

		# not our route → default behaviour
		return orig_handle()

	frappe.api.handle = patched_handle
	frappe._fastapi_patch_done = True


_install_patch()
