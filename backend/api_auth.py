from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from core import db, hash_password, issue_token, require_admin, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginInput(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class PasswordInput(BaseModel):
    oldPassword: str
    newPassword: str = Field(min_length=10)


@router.post("/login")
async def login(payload: LoginInput, request: Request, response: Response):
    user = await db.users.find_one({"username": payload.username}, {"_id": 0})
    if not user or not verify_password(payload.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    response.set_cookie("ah_session", issue_token(user), httponly=True, secure=secure,
                        samesite="lax", max_age=12 * 3600, path="/")
    return {"username": user["username"], "name": user["name"]}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("ah_session", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user=Depends(require_admin)):
    return {"username": user["username"], "name": user["name"]}


@router.post("/change-password")
async def change_password(payload: PasswordInput, user=Depends(require_admin)):
    if not verify_password(payload.oldPassword, user["passwordHash"]):
        raise HTTPException(400, "Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"passwordHash": hash_password(payload.newPassword)}, "$inc": {"sessionVersion": 1}})
    return {"ok": True, "message": "Password changed. Please sign in again."}