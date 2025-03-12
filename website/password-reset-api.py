from fastapi import FastAPI, HTTPException, status
from password_models import PasswordResetRequest, PasswordResetResponse

app = FastAPI(
    title="Password Reset API",
    description="A simple API for password reset functionality",
    version="1.0.0",
)

@app.post(
    "/password-reset",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset user password",
    description="Endpoint to request a password reset for a user account",
)
async def password_reset(request: PasswordResetRequest):
    """
    Reset a user's password:
    
    - **email**: Email address of the user requesting password reset
    - **Returns**: Confirmation that a reset link has been sent
    """    
    print("-"*50)
    print(f"Password Reset for: {request.email}")
    print("-"*50)
    # In a real application, you would:
    # 1. Validate the email exists in your database
    # 2. Generate a secure token
    # 3. Store the token with an expiration time
    # 4. Send an email with a reset link
    
    # For this simple example, we'll just return a success response
    # Email validation is handled by Pydantic's EmailStr
    
    return PasswordResetResponse(
        message="Password reset link sent",
        email=request.email
    )

@app.get("/")
async def root():
    """Root endpoint that redirects to the API documentation."""
    return {"message": "Welcome to the Password Reset API. Visit /docs for the API documentation."}
