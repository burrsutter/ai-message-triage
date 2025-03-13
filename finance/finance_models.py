from pydantic import BaseModel, EmailStr, Field
from typing import List
from datetime import date

class FinanceRequest(BaseModel):
    """
    Model for finance request.
    """
    email: EmailStr = Field(
        ...,
        description="Email address of the user requesting financal data",
        example="user@example.com"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

class FinanceRecord(BaseModel):
    """
    Model representing a single finance record.
    """
    order_id: int = Field(..., description="Unique identifier for the order")
    customer_name: str = Field(..., description="Name of the customer")
    order_date: date = Field(..., description="Date when the order was placed")
    order_number: str = Field(..., description="Unique order number")
    status: str = Field(..., description="Current status of the order")
    total_amount: float = Field(..., description="Total amount for the order")

class FinanceResponse(BaseModel):
    """
    Model for finance API response.
    """
    records: List[FinanceRecord] = Field(..., description="List of finance records")

    class Config:
        json_schema_extra = {
            "example": {
                "records": [
                    {
                        "order_id": 1234,
                        "customer_name": "John Doe",
                        "order_date": "2024-03-13",
                        "order_number": "ORD-5678",
                        "status": "Completed",
                        "total_amount": 199.99
                    }
                ]
            }
        }