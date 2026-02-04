"""Gemini 2.0 Flash LLM client using google-genai SDK."""

from typing import Any, Dict, List, Optional

import structlog
from google import genai
from google.genai import types

from app.config import get_settings

logger = structlog.get_logger(__name__)


class GeminiClient:
    """Wrapper for Gemini 2.0 Flash API calls."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self.model = self.settings.gemini_model
        logger.info("gemini_client_initialized", model=self.model)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
    ) -> str:
        """Generate a response from Gemini.

        Args:
            prompt: User prompt text.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature (0.0-2.0).
            max_output_tokens: Maximum tokens in response.

        Returns:
            Generated text response.
        """
        logger.info("generating_response", prompt_length=len(prompt))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            text = response.text or ""
            logger.info("response_generated", response_length=len(text))
            return text

        except Exception as e:
            logger.error("generation_failed", error=str(e))
            raise

    def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
    ) -> str:
        """Generate a response with conversation history.

        Args:
            messages: List of {"role": "user"|"model", "content": "..."} dicts.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature.
            max_output_tokens: Maximum tokens in response.

        Returns:
            Generated text response.
        """
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "assistant":
                role = "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])],
                )
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error("generation_with_history_failed", error=str(e))
            raise

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        """Generate a JSON response from Gemini.

        Args:
            prompt: User prompt text.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature.

        Returns:
            JSON string response.
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=4096,
            response_mime_type="application/json",
        )
        if system_instruction:
            config.system_instruction = system_instruction

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return response.text or "{}"
        except Exception as e:
            logger.error("json_generation_failed", error=str(e))
            raise

    def test_connection(self) -> bool:
        """Test Gemini API connection.

        Returns:
            True if connection is successful.
        """
        try:
            response = self.generate("Say 'OK' if you can hear me.", temperature=0.0)
            logger.info("gemini_connection_test_passed", response=response[:50])
            return bool(response)
        except Exception as e:
            logger.error("gemini_connection_test_failed", error=str(e))
            return False


# Singleton instance
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create the Gemini client singleton."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
