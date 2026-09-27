"""Common base for all domain models."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base model. Defaulted fields are always serialized, so OpenAPI marks them required and
    the generated frontend types are not needlessly optional."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
