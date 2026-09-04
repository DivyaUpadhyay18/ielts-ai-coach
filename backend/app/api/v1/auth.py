"""
Authentication endpoints for user registration, login, token refresh, logout,
password reset, and profile management.
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone
from app.db.supabase import supabase
from app.core.security import (
    verify_password,
    get_password_hash,
    validate_password_strength,
    create_tokens,
    decode_token,
    limiter,
)
from app.core.config import settings
from app.models.auth import (
    UserCreate,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    PasswordResetRequest,
    PasswordReset,
    ChangePassword,
    ErrorResponse,
)
from app.api.deps import get_current_user, get_current_user_profile

router = APIRouter()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        201: {"description": "User created successfully"},
        400: {"description": "Validation error or email already exists"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    user_data: UserCreate,
    request: Request,  # Required by slowapi
):
    """
    Register a new user with email and password.
    
    - Validates email format and uniqueness
    - Validates password strength
    - Hashes password with bcrypt
    - Creates user in Supabase
    - Returns JWT access and refresh tokens
    """
    try:
        print("REGISTER: entered register() handler", flush=True)
        # Validate password strength
        password_error = validate_password_strength(user_data.password)
        if password_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=password_error,
            )
        
        # Check if email already exists.
        # NOTE: deliberately NOT using .maybe_single() here. postgrest-py 0.17.2
        # fails to parse PostgREST's 204 No Content response when zero rows
        # match, raising "Missing response" instead of returning empty data.
        # A plain select returns a list (empty when no rows match).
        # The Supabase client is synchronous (blocking), so it MUST NOT be
        # called directly inside an async route: a slow/unresponsive PostgREST
        # call would freeze the entire event loop on a single-worker
        # deployment. Run it in a thread and enforce a hard 10-second timeout.
        print("REGISTER: starting email-exists check", flush=True)
        try:
            existing = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: supabase.table("users")
                    .select("id")
                    .eq("email", user_data.email)
                    .execute()
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Email verification timed out. Please try again.",
            )
        print("REGISTER: email-exists check done", flush=True)
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists",
            )
        
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user in Supabase Auth.
        # The Supabase admin client is synchronous (blocking), so it MUST NOT be
        # called directly inside an async route: on a single-worker deployment a
        # slow/unresponsive Supabase Admin API would freeze the entire event
        # loop. Run it in a thread and enforce a hard 15-second timeout.
        print("REGISTER: starting create_user (Supabase Admin API)", flush=True)
        try:
            auth_result = await asyncio.wait_for(
                asyncio.to_thread(
                    supabase.auth.admin.create_user,
                    email=user_data.email,
                    password=user_data.password,
                    email_confirm=True,
                    user_metadata={"full_name": user_data.full_name},
                ),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="User creation timed out. Please try again.",
            )
        print("REGISTER: create_user done", flush=True)

        user_id = auth_result.user.id
        
        # Create user profile in our users table
        now = datetime.now(timezone.utc).isoformat()
        user_profile = {
            "id": user_id,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "password_hash": hashed_password,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        
        # Create user profile in our users table.
        # This is a blocking Supabase call, so it MUST NOT be awaited directly
        # inside an async route: on a single-worker deployment a slow/hung
        # PostgREST insert would freeze the entire event loop. Run it in a
        # thread and enforce a hard 10-second timeout.
        print("REGISTER: starting users-table insert", flush=True)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: supabase.table("users").insert(user_profile).execute()
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Profile creation (users-table insert) timed out. Please try again.",
            )
        print("REGISTER: users-table insert done", flush=True)
        
        # Generate tokens
        access_token, refresh_token = create_tokens(user_id, user_data.email, role="user")
        
        # Store refresh token.
        # This is a blocking Supabase call, so it MUST NOT be awaited directly
        # inside an async route: on a single-worker deployment a slow/hung
        # PostgREST insert would freeze the entire event loop. Run it in a
        # thread and enforce a hard 10-second timeout.
        print("REGISTER: starting refresh_tokens insert", flush=True)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: supabase.table("refresh_tokens").insert({
                        "user_id": user_id,
                        "token_hash": get_password_hash(refresh_token),
                        "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).isoformat(),
                        "created_at": now,
                    }).execute()
                ),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Session creation (refresh_tokens insert) timed out. Please try again.",
            )
        print("REGISTER: refresh_tokens insert done", flush=True)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    login_data: UserLogin,
    request: Request,  # Required by slowapi
):
    """
    Authenticate a user with email and password.
    
    - Verifies credentials against stored hash
    - Returns JWT access and refresh tokens
    """
    try:
        # Find user by email.
        # NOTE: deliberately NOT using .maybe_single() here: postgrest-py 0.17.2
        # fails to parse PostgREST's 204 No Content response when zero rows
        # match, raising "Missing response" instead of returning empty data.
        # A plain select returns a list (empty when no rows match).
        result = supabase.table("users").select("*").eq("email", login_data.email).execute()
        
        if not result.data or len(result.data) == 0:
            # Use generic message to prevent email enumeration
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        user = result.data[0]
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled. Please contact support.",
            )
        
        # Verify password
        if not verify_password(login_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Generate tokens
        role = user.get("role", "user")
        access_token, refresh_token = create_tokens(user["id"], user["email"], role=role)
        
        # Store refresh token
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("refresh_tokens").insert({
            "user_id": user["id"],
            "token_hash": get_password_hash(refresh_token),
            "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).isoformat(),
            "created_at": now,
        }).execute()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}",
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        200: {"description": "Tokens refreshed successfully"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
):
    """
    Refresh an expired access token using a valid refresh token.
    
    - Validates the refresh token
    - Issues new access and refresh token pair
    - Invalidates the old refresh token
    """
    try:
        # Decode the refresh token
        payload = decode_token(refresh_data.refresh_token, expected_type="refresh")
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        
        # Verify the refresh token exists in our database
        stored_tokens = supabase.table("refresh_tokens").select("*").eq("user_id", user_id).execute()
        
        valid_token_found = False
        for stored in stored_tokens.data or []:
            if verify_password(refresh_data.refresh_token, stored["token_hash"]):
                valid_token_found = True
                # Delete the old refresh token (rotation)
                supabase.table("refresh_tokens").delete().eq("id", stored["id"]).execute()
                break
        
        if not valid_token_found:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )
        
        # Fetch user role for token generation
        user_result = supabase.table("users").select("role").eq("id", user_id).single().execute()
        role = user_result.data.get("role", "user") if user_result.data else "user"

        # Generate new tokens
        access_token, new_refresh_token = create_tokens(user_id, email, role=role)
        
        # Store new refresh token
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("refresh_tokens").insert({
            "user_id": user_id,
            "token_hash": get_password_hash(new_refresh_token),
            "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)).isoformat(),
            "created_at": now,
        }).execute()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}",
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout and invalidate refresh tokens",
    responses={
        200: {"description": "Logged out successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def logout(
    user_id: str = Depends(get_current_user),
):
    """
    Logout a user by invalidating all their refresh tokens.
    """
    try:
        # Delete all refresh tokens for the user
        supabase.table("refresh_tokens").delete().eq("user_id", user_id).execute()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}",
        )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    responses={
        200: {"description": "User profile retrieved"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(
    user: UserResponse = Depends(get_current_user_profile),
):
    """
    Get the currently authenticated user's profile.
    """
    return user


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    responses={
        200: {"description": "Password reset email sent"},
        429: {"description": "Too many requests"},
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def forgot_password(
    reset_data: PasswordResetRequest,
    request: Request,  # Required by slowapi
):
    """
    Request a password reset email.
    Always returns success to prevent email enumeration.
    """
    try:
        # Check if user exists.
        # NOTE: deliberately NOT using .maybe_single() here: postgrest-py 0.17.2
        # fails to parse PostgREST's 204 No Content response when zero rows
        # match, raising "Missing response" instead of returning empty data.
        # A plain select returns a list (empty when no rows match).
        result = supabase.table("users").select("id, email").eq("email", reset_data.email).execute()
        
        if result.data and len(result.data) > 0:
            user_row = result.data[0]
            # Generate a password reset token (short-lived)
            from app.core.security import create_access_token
            from datetime import timedelta
            
            reset_token = create_access_token(
                data={"sub": user_row["id"], "email": user_row["email"], "purpose": "password_reset"},
                expires_delta=timedelta(hours=1),
            )
            
            # Store the reset token
            now = datetime.now(timezone.utc).isoformat()
            supabase.table("password_reset_tokens").insert({
                "user_id": user_row["id"],
                "token_hash": get_password_hash(reset_token),
                "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + __import__("datetime").timedelta(hours=1)).isoformat(),
                "is_used": False,
                "created_at": now,
            }).execute()
            
            # In production, send email here with the reset link
            # reset_link = f"https://yourdomain.com/reset-password?token={reset_token}"
            # Send email via SendGrid, Resend, etc.
            
            print(f"Password reset token for {user_row['email']}: {reset_token}")
        
        # Always return success to prevent email enumeration
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
        }
        
    except Exception as e:
        # Still return success for security
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
        }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    responses={
        200: {"description": "Password reset successfully"},
        400: {"description": "Invalid or expired token"},
    },
)
async def reset_password(
    reset_data: PasswordReset,
):
    """
    Reset password using a valid reset token.
    """
    try:
        # Decode the reset token
        payload = decode_token(reset_data.token, expected_type="access")
        
        if payload.get("purpose") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token",
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token",
            )
        
        # Verify the token exists in our database and is not used
        stored_tokens = supabase.table("password_reset_tokens").select("*").eq("user_id", user_id).eq("is_used", False).execute()
        
        valid_token = None
        for stored in stored_tokens.data or []:
            if verify_password(reset_data.token, stored["token_hash"]):
                valid_token = stored
                break
        
        if not valid_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or has already been used",
            )
        
        # Validate new password strength
        password_error = validate_password_strength(reset_data.new_password)
        if password_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=password_error,
            )
        
        # Update password
        new_hash = get_password_hash(reset_data.new_password)
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("users").update({
            "password_hash": new_hash,
            "updated_at": now,
        }).eq("id", user_id).execute()
        
        # Mark token as used
        supabase.table("password_reset_tokens").update({"is_used": True}).eq("id", valid_token["id"]).execute()
        
        # Invalidate all refresh tokens (force re-login)
        supabase.table("refresh_tokens").delete().eq("user_id", user_id).execute()
        
        return {"message": "Password has been reset successfully. Please log in with your new password."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password reset failed: {str(e)}",
        )


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password (authenticated)",
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "Invalid current password"},
        401: {"description": "Not authenticated"},
    },
)
async def change_password(
    password_data: ChangePassword,
    user_id: str = Depends(get_current_user),
):
    """
    Change password for the currently authenticated user.
    Requires current password verification.
    """
    try:
        # Get current user data
        result = supabase.table("users").select("password_hash").eq("id", user_id).single().execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        # Verify current password
        if not verify_password(password_data.current_password, result.data["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        
        # Validate new password strength
        password_error = validate_password_strength(password_data.new_password)
        if password_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=password_error,
            )
        
        # Update password
        new_hash = get_password_hash(password_data.new_password)
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("users").update({
            "password_hash": new_hash,
            "updated_at": now,
        }).eq("id", user_id).execute()
        
        # Invalidate all refresh tokens (force re-login)
        supabase.table("refresh_tokens").delete().eq("user_id", user_id).execute()
        
        return {"message": "Password changed successfully. Please log in again."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}",
        )
