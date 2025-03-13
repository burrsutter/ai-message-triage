from fastapi import FastAPI, HTTPException, status
from datetime import date
from finance_models import FinanceRequest, FinanceResponse, FinanceRecord

app = FastAPI(
    title="Finance API",
    description="A simple API for Finance functionality",
    version="1.0.0",
)

@app.post(
    "/order-history",
    response_model=FinanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Request order history",
    description="Endpoint to a customer's order history",
)
async def order_history(request: FinanceRequest):
    """
    Customer's order history
    
    - **email**: Email address of the customer
    - **Returns**:
    """    
    print("-"*50)
    print(f"Order History: {request.email}")
    print("-"*50)
    
    return FinanceResponse(
        records=[  # Ensuring it's a list inside `records`
            FinanceRecord(
                order_id=100,
                customer_name="Customer Name",
                order_date=date.today(),
                order_number="ORD-1234",
                status="Completed",
                total_amount=100.00,
            )
        ]
    )

@app.get("/")
async def root():
    """Root endpoint that redirects to the API documentation."""
    return {"message": "Welcome to the Finance API. Visit /docs for the API documentation."}
