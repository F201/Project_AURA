from pydantic import BaseModel

class SystemStatus(BaseModel):
    state: str
