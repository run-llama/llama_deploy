from pydantic import BaseModel


class Topic(BaseModel):
    """Light data class for AWS SNS Topic."""

    arn: str
    name: str


class Queue(BaseModel):
    """Light data class for AWS SQS Queue."""

    arn: str
    url: str
    name: str


class Subscription(BaseModel):
    """Light data class for AWS SNS Subscription."""

    arn: str
