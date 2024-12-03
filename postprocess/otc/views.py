from typing import List
from pydantic import BaseModel


class ExaminedUrl(BaseModel):
    statics: List[str]
    dynamics: List[str]