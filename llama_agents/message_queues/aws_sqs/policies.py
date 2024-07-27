from typing import Dict
import json


def get_attributes_with_topic_policy(queue_arn: str, topic_arn: str) -> Dict[str, str]:
    """
    Add the necessary access policy to a queue, so it can receive messages from
    an SNS topic.

    Parameters:
    queue_arn: The queue resource.
    topic_arn: The ARN of the topic.

    Returns:
    None.
    """
    return {
        "Policy": json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "test-sid",
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "SQS:SendMessage",
                        "Resource": queue_arn,
                        "Condition": {"ArnLike": {"aws:SourceArn": topic_arn}},
                    }
                ],
            }
        )
    }
