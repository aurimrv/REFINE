from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterModel(BaseModel):
    """Represents a single OpenAPI parameter (path, query, header, cookie)."""

    name: str
    location: str = Field(alias="in")
    required: bool = False
    schema_: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    description: Optional[str] = None
    example: Optional[Any] = None
    examples: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class ResponseModel(BaseModel):
    """Represents a single OpenAPI response object."""

    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    examples: Optional[Dict[str, Any]] = None


class OperationModel(BaseModel):
    """Represents an HTTP operation (GET, POST, etc.) on a path."""

    operation_id: Optional[str] = Field(default=None, alias="operationId")
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[Dict[str, Any]]] = None
    request_body: Optional[Dict[str, Any]] = Field(default=None, alias="requestBody")
    responses: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

    model_config = {"populate_by_name": True}


class EndpointInfo(BaseModel):
    """Aggregated information about a single endpoint for LLM processing."""

    path: str
    method: str
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    response_codes: List[str] = Field(default_factory=list)
    responses: Dict[str, Any] = Field(default_factory=dict)
