from pydantic import BaseModel, EmailStr, Field

class PasswordResetRequest(BaseModel):
    """
    Model for password reset request.
    """
    email: EmailStr = Field(
        ...,
        description="Email address of the user requesting password reset",
        example="user@example.com"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

class PasswordResetResponse(BaseModel):
    """
    Model for password reset response.
    """
    message: str = Field(
        ...,
        description="Status message about the password reset request",
        example="Password reset link sent"
    )
    email: str = Field(
        ...,
        description="Email address to which the reset link was sent",
        example="user@example.com"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Password reset link sent",
                "email": "user@example.com"
            }
        }


class ForgotUserIDResponse(BaseModel):
    """
    Model for forgot user id response.
    """
    message: str = Field(
        ...,
        description="Status message about the forogot userid  request",
        example="Email reminder"
    )
    email: str = Field(
        ...,
        description="Email address to which the reset link was sent",
        example="user@example.com"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Remdinder email",
                "email": "user@example.com"
            }
        }
