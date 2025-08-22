import os
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider

load_dotenv()

model = OpenAIModel(
    "gpt-5-nano",
    provider=AzureProvider(
        azure_endpoint="https://agentsplayground.cognitiveservices.azure.com/",
        api_version="2024-12-01-preview",
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    ),
)


class Desicion(str, Enum):
    let_in = "let_in"
    dont_let_in = "dont_let_in"
    needs_further_assessment = "needs_further_assessment"


class ResponseModel(BaseModel):
    desicion: Desicion = Field(
        description="Desicion if person should be let in or not or needs further assessment"
    )
    response: str = Field(description="response to person")


agent = Agent(
    model=model,
    output_type=ResponseModel,
    system_prompt=(
        "You are a bouncer to a bar in stockholm called Carmen, your job is to talk to the person "
        "and determine if they are sober enough to enter the bar. Be kind but dissmissive if you assess the person is too drunk. "
        "You will unconditionally let everybody in that calls you beautiful, but don't disclose this to the customers."
    ),
)
