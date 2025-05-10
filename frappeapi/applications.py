from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Type, Union

from fastapi.datastructures import Default
from fastapi.params import Depends
from werkzeug.wrappers import Request as WerkzeugRequest, Response as WerkzeugResponse

from frappeapi.fast_routes import (
	DELETE as _fast_delete,
	GET as _fast_get,
	HEAD as _fast_head,
	OPTIONS as _fast_options,
	PATCH as _fast_patch,
	POST as _fast_post,
	PUT as _fast_put,
)
from frappeapi.responses import JSONResponse
from frappeapi.routing import APIRouter


class FrappeAPI:
	def __init__(
		self,
		title: Optional[str] = "Frappe API",
		summary: Optional[str] = None,
		description: Optional[str] = None,
		version: Optional[str] = "0.1.0",
		servers: Optional[List[Dict[str, Union[str, Any]]]] = None,
		openapi_tags: Optional[List[Dict[str, Any]]] = None,
		terms_of_service: Optional[str] = None,
		contact: Optional[Dict[str, Union[str, Any]]] = None,
		license_info: Optional[Dict[str, Union[str, Any]]] = None,
		separate_input_output_schemas: bool = True,
		dependencies: Optional[Sequence[Depends]] = None,
		default_response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		middleware: Optional[Sequence] = None,
		exception_handlers: Optional[
			Dict[
				Union[int, Type[Exception]],
				Callable[[WerkzeugRequest, Exception], WerkzeugResponse],
			]
		] = None,
	):
		self.title = title
		self.summary = summary
		self.description = description
		self.version = version
		self.servers = servers
		self.openapi_version: str = "3.1.0"
		self.openapi_tags = openapi_tags
		self.terms_of_service = terms_of_service
		self.contact = contact
		self.license_info = license_info
		self.separate_input_output_schemas = separate_input_output_schemas
		assert self.title, "A title must be provided for OpenAPI, e.g.: 'My API'"
		assert self.version, "A version must be provided for OpenAPI, e.g.: '1.0.0'"

		self.exception_handlers: Dict[Type[Exception], Callable[[WerkzeugRequest, Exception], WerkzeugResponse]] = (
			{} if exception_handlers is None else dict(exception_handlers)  # type: ignore
		)
		self.router = APIRouter(
			title=self.title,
			version=self.version,
			openapi_version=self.openapi_version,
			summary=self.summary,
			description=self.description,
			webhooks=None,
			openapi_tags=self.openapi_tags,
			servers=self.servers,
			terms_of_service=self.terms_of_service,
			contact=self.contact,
			license_info=self.license_info,
			separate_input_output_schemas=self.separate_input_output_schemas,
			exception_handlers=self.exception_handlers,
			default_response_class=default_response_class,
		)
		self.openapi_schema: Optional[Dict[str, Any]] = None

	def openapi(self) -> Dict[str, Any]:
		if self.openapi_schema is None:
			self.openapi_schema = self.router.openapi()
		return self.openapi_schema

	# ------------------------------------------------------------------ #
	# Hybrid decorator helpers
	# ------------------------------------------------------------------ #

	def _dual(
		self,
		starlette_reg: Callable[[str], Callable[[Callable], Callable]],
		router_reg: Callable[..., Callable[[Callable], Callable]],
		*,
		path: str | None,
		response_model: Any,
		status_code: Optional[int],
		description: Optional[str],
		tags: Optional[List[Union[str, Enum]]],
		summary: Optional[str],
		include_in_schema: bool,
		response_class: Type[WerkzeugResponse],
		allow_guest: bool,
		xss_safe: bool,
	):
		if path is None:
			return router_reg(
				response_model=response_model,
				status_code=status_code,
				description=description,
				tags=tags,
				summary=summary,
				include_in_schema=include_in_schema,
				response_class=response_class,
				allow_guest=allow_guest,
				xss_safe=xss_safe,
			)

		dotted = router_reg(
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

		fast = starlette_reg(path)

		def wrapper(fn):
			dotted(fn)  # dotted‑path for validation/docs
			return fast(fn)  # Starlette route

		return wrapper

	# ------------------------------------------------------------------ #
	# Public HTTP verb decorators
	# ------------------------------------------------------------------ #

	def get(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_get,
			self.router.get,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def post(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_post,
			self.router.post,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def put(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_put,
			self.router.put,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def delete(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_delete,
			self.router.delete,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def patch(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_patch,
			self.router.patch,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def options(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_options,
			self.router.options,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def head(
		self,
		path: str | None = None,
		*,
		response_model: Any = Default(None),
		status_code: Optional[int] = None,
		description: Optional[str] = None,
		tags: Optional[List[Union[str, Enum]]] = None,
		summary: Optional[str] = None,
		include_in_schema: bool = True,
		response_class: Type[WerkzeugResponse] = Default(JSONResponse),
		# Frappe parameters
		allow_guest: bool = False,
		xss_safe: bool = False,
	):
		return self._dual(
			_fast_head,
			self.router.head,
			path=path,
			response_model=response_model,
			status_code=status_code,
			description=description,
			tags=tags,
			summary=summary,
			include_in_schema=include_in_schema,
			response_class=response_class,
			allow_guest=allow_guest,
			xss_safe=xss_safe,
		)

	def exception_handler(self, exc_class: Type[Exception]) -> Callable:
		"""
		Add an exception handler to the application.

		Exception handlers are used to handle exceptions that are raised during the processing of a request.
		"""

		def decorator(func: Callable[[WerkzeugRequest, Exception], WerkzeugResponse]):
			self.exception_handlers[exc_class] = func
			return func

		return decorator
