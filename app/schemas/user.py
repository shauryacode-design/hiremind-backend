from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):

    first_name: str

    last_name: str