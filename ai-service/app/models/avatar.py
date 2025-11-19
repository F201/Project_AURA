from pydantic import BaseModel

class AvatarAction(BaseModel):
    action: str

class AvatarResponse(BaseModel):
    status: str
