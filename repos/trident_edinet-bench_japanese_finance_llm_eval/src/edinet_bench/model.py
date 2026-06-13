import backoff
import anthropic
import openai
from openai import OpenAI
import os

from dataclasses import dataclass


@dataclass
class GenerationConfig:
    max_tokens: int = 4096
    temperature: float = 0.0


class Model:
    def __init__(self, model_id: str, system_prompt: str):
        self.model_id = model_id
        self.system_prompt = system_prompt

    def get_completion(
        self, prompt: str, gen_kwargs: GenerationConfig = GenerationConfig()
    ) -> str:
        raise NotImplementedError("This method should be overridden by subclasses.")


class OpenAIModel(Model):
    def __init__(
        self,
        model_name: str = "gpt-4o-2024-05-13",
        system_prompt: str = "You are a helpful assistant.",
    ):
        self.model_name = model_name
        self.client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.system_prompt = system_prompt

    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APIError, openai.Timeout),
        max_tries=5,
    )
    def get_completion(
        self, prompt: str, gen_kwargs: GenerationConfig = GenerationConfig()
    ) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": [{"type": "text", "text": prompt}]},
        ]
        if self.model_name == "o4-mini-2025-04-16":
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            )
        else:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=gen_kwargs.max_tokens,
                temperature=gen_kwargs.temperature,
                seed=0,
            )
        return response.choices[0].message.content


class AnthropicModel(Model):
    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20241022",
        system_prompt: str = "You are a helpful assistant.",
    ):
        self.model_name = model_name
        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.system_prompt = system_prompt

    @backoff.on_exception(
        backoff.expo,
        (anthropic.RateLimitError, anthropic.APIError, anthropic.InternalServerError),
        max_tries=5,
    )
    def get_completion(
        self, prompt: str, gen_kwargs: GenerationConfig = GenerationConfig()
    ) -> str:
        response = self.client.messages.create(
            model=self.model_name,
            system=self.system_prompt,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            max_tokens=gen_kwargs.max_tokens,
            temperature=gen_kwargs.temperature,
        )
        return response.content[0].text


class OpenRouterModel(Model):
    def __init__(
        self,
        model_name: str = "deepseek/deepseek-r1",
        system_prompt: str = "You are a helpful assistant.",
    ):
        self.model_name = model_name
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )
        self.system_prompt = system_prompt

    @backoff.on_exception(
        backoff.expo,
        (openai.RateLimitError, openai.APIError, openai.Timeout),
        max_tries=5,
    )
    def get_completion(
        self, prompt: str, gen_kwargs: GenerationConfig = GenerationConfig()
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=gen_kwargs.max_tokens,
            temperature=gen_kwargs.temperature,
        )
        return response.choices[0].message.content


MODEL_TABLE: dict[str, Model] = {
    "claude-3-5-sonnet-20241022": AnthropicModel,
    "claude-3-7-sonnet-20250219": AnthropicModel,
    "claude-3-5-haiku-20241022": AnthropicModel,
    "gpt-4o-2024-11-20": OpenAIModel,
    "o4-mini-2025-04-16": OpenAIModel,
    "deepseek/deepseek-r1": OpenRouterModel,
    "deepseek/deepseek-chat": OpenRouterModel,
}


if __name__ == "__main__":
    # Example usage
    model_id = "claude-3-5-haiku-20241022"
    model = MODEL_TABLE[model_id](
        model_name=model_id,
        system_prompt="You are a helpful assistant.",
    )

    prompt = "What is the meaning of the annual report of a company?"

    print(f"MODEL Response: {model.get_completion(prompt)}")
