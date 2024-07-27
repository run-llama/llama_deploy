from pydantic import BaseModel


class BaseAWSResource(BaseModel):
    arn: str
