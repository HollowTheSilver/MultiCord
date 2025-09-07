"""
Authentication Router
====================

OAuth2 device flow and token management endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

from platform_api.schemas.auth_schemas import (
    DeviceCodeRequest,
    DeviceCodeResponse,
    TokenRequest,
    TokenResponse,
    TokenErrorResponse
)
from platform_core.services.auth_service import DeviceFlowService
from platform_core.services.token_service import TokenService


router = APIRouter()

# Initialize services (in production, use dependency injection)
device_flow_service = DeviceFlowService()
token_service = TokenService()


@router.post("/device", response_model=DeviceCodeResponse)
async def request_device_code(request: DeviceCodeRequest):
    """Request device and user codes for OAuth2 device flow."""
    scopes = request.scope.split() if request.scope else ["bot:read", "bot:write"]
    
    response = await device_flow_service.create_device_authorization(scopes)
    
    return DeviceCodeResponse(
        device_code=response.device_code,
        user_code=response.user_code,
        verification_uri=response.verification_uri,
        verification_uri_complete=response.verification_uri_complete,
        expires_in=response.expires_in,
        interval=response.interval
    )


@router.post("/token")
async def exchange_token(request: TokenRequest):
    """Exchange device code or refresh token for access tokens."""
    
    if request.grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        # Device code flow
        if not request.device_code:
            return JSONResponse(
                status_code=400,
                content=TokenErrorResponse(
                    error="invalid_request",
                    error_description="Missing device_code"
                ).model_dump()
            )
        
        error, token_response = await device_flow_service.poll_for_token(request.device_code)
        
        if error:
            return JSONResponse(
                status_code=400,
                content=TokenErrorResponse(
                    error=error,
                    error_description=f"Device flow error: {error}"
                ).model_dump()
            )
        
        # Generate real JWT tokens
        # For now, using placeholder from device_flow_service
        return TokenResponse(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            token_type=token_response.token_type,
            expires_in=token_response.expires_in,
            scope=token_response.scope
        )
    
    elif request.grant_type == "refresh_token":
        # Refresh token flow
        if not request.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing refresh_token"
            )
        
        result = token_service.rotate_refresh_token(request.refresh_token)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        access_token, refresh_token = result
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=3600,
            scope="bot:read bot:write"
        )
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {request.grant_type}"
        )