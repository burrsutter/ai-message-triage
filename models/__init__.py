from pydantic import BaseModel, Field


from datetime import datetime
from typing import Optional, Dict, Any

class AnalyzedEmail(BaseModel):
    reason: str
    sentiment: Optional[str]
    customer_name: Optional[str]
    email_address: Optional[str]
    product_name: Optional[str]
    escalate: bool

class Message(BaseModel):
    id: str
    filename: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    comment: Optional[AnalyzedEmail] = None
    error: Optional[str] = None


