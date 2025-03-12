from httpx import stream
from pydantic import BaseModel, Field


from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class Route(str, Enum):
    support = "support"
    finance = "finance"
    website = "website"
    unknown = "unknown"

class SelectedRoute(BaseModel):
    route: Route
    reason: str
    escalation_required: bool

class SupportResponse(BaseModel):
    response: str
    source: Optional[str]

class WebsiteResponse(BaseModel):
    response: str
    toolinvoked: bool
        
class StructuredObject(BaseModel):
    reason: str
    sentiment: Optional[str]
    company_id: Optional[str]
    company_name: Optional[str]
    customer_name: Optional[str]
    country: Optional[str]
    email_address: Optional[str]
    phone: Optional[str]
    product_name: Optional[str]
    escalate: bool

class OuterWrapper(BaseModel):
    id: str
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    structured: Optional[StructuredObject] = None
    route: Optional[Route] = None
    support: Optional[SupportResponse] = None
    website: Optional[WebsiteResponse] = None
    comment: Optional[str] = None
    error: list = Field(default_factory=list)
