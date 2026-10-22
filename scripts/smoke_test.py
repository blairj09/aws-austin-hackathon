"""Check that your AWS credentials can call the Bedrock model through chatlas.

    uv run python scripts/smoke_test.py
    BEDROCK_MODEL_ID=us.openai.gpt-5.6-sol uv run python scripts/smoke_test.py
"""

import boto3

from caregivers.config import MODEL_ID, REGION, make_chat

identity = boto3.client("sts", region_name=REGION).get_caller_identity()
print(f"AWS identity: {identity['Arn']}")
print(f"Model: {MODEL_ID} in {REGION}")

chat = make_chat("Reply with exactly: OK")
print("Response:", chat.chat("Are you there?", echo="none").get_content().strip())
