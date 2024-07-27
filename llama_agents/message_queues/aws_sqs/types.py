from llama_agents.message_queues.aws_sqs.base import BaseAWSResource


class Topic(BaseAWSResource):
    """Light data class for AWS SNS Topic."""

    name: str


class Queue(BaseAWSResource):
    """Light data class for AWS SQS Queue."""

    url: str
    name: str


class Subscription(BaseAWSResource):
    """Light data class for AWS SNS Subscription."""
