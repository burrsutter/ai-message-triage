from pydantic import BaseModel, Field


from datetime import datetime
from typing import Optional, Dict, Any

class AnalyzedMessage(BaseModel):
    reason: str
    sentiment: Optional[str]
    company_name: Optional[str]
    customer_name: Optional[str]    
    email_address: Optional[str]
    phone: Optional[str]
    product_name: Optional[str]
    escalate: bool

class Message(BaseModel):
    id: str
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    structured: Optional[AnalyzedMessage] = None
    comment: Optional[str] = None
    error: list = Field(default_factory=list)
