from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import AgeGroup


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    gender: str
    gender_probability: float
    age: int
    age_group: AgeGroup
    country_id: str
    country_name: str
    country_probability: float
    created_at: datetime


class ProfileListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    gender: str
    gender_probability: float
    age: int
    age_group: AgeGroup
    country_id: str
    country_name: str
    country_probability: float
    created_at: datetime
