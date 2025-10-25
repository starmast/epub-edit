"""LLM service for interacting with OpenAI-compatible APIs."""
import asyncio
import httpx
from typing import Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with LLM APIs."""

    def __init__(
        self,
        api_endpoint: str,
        api_key: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_retries: int = 3,
    ):
        """
        Initialize LLM service.

        Args:
            api_endpoint: API endpoint URL
            api_key: API key
            model: Model name
            temperature: Temperature for generation
            max_retries: Maximum number of retries on failure
        """
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

        # Ensure endpoint has the chat completions path
        if not self.api_endpoint.endswith("/chat/completions"):
            self.api_endpoint = f"{self.api_endpoint}/chat/completions"

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Generate completion from LLM.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response

        Returns:
            Response dictionary with 'content' and 'usage'

        Raises:
            Exception: If API call fails after retries
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                # Log request details for debugging
                logger.debug(f"Sending request to {self.api_endpoint}")
                logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        self.api_endpoint,
                        headers=headers,
                        json=payload,
                    )

                    response.raise_for_status()
                    result = response.json()

                    # Extract content and usage
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})

                    return {
                        "content": content,
                        "usage": usage,
                        "model": result.get("model", self.model),
                    }

            except httpx.HTTPStatusError as e:
                error_body = ""
                try:
                    error_body = e.response.text
                except:
                    pass

                logger.error(f"HTTP error on attempt {attempt + 1}: {e.response.status_code} - {error_body}")

                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Rate limited, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                elif e.response.status_code >= 500:  # Server error
                    wait_time = 2 ** attempt
                    logger.info(f"Server error, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # Client error, don't retry - include response body in error
                    raise Exception(f"Client error {e.response.status_code}: {error_body or str(e)}")

            except (httpx.RequestError, json.JSONDecodeError) as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")

                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise

        raise Exception(f"Failed to get completion after {self.max_retries} attempts")

    async def edit_chapter(
        self,
        chapter_content: str,
        system_prompt: str,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Edit a chapter using the LLM.

        Args:
            chapter_content: The chapter content to edit
            system_prompt: System prompt with editing instructions
            max_tokens: Maximum tokens in response

        Returns:
            Dictionary with edit commands and usage stats
        """
        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Please edit the following chapter content:\n\n{chapter_content}",
            },
        ]

        # Get completion
        result = await self.generate_completion(messages, max_tokens)

        return {
            "edits": result["content"],
            "usage": result["usage"],
            "model": result["model"],
        }

    @staticmethod
    async def test_connection(
        api_endpoint: str, api_key: str, model: str = "gpt-4"
    ) -> Dict:
        """
        Test API connection.

        Args:
            api_endpoint: API endpoint URL
            api_key: API key
            model: Model name to test

        Returns:
            Dictionary with success status and message
        """
        try:
            service = LLMService(api_endpoint, api_key, model)

            messages = [
                {"role": "user", "content": "Respond with 'OK' if you can read this."}
            ]

            result = await service.generate_completion(messages, max_tokens=10)

            return {
                "success": True,
                "message": "Connection successful",
                "model": result.get("model"),
            }

        except Exception as e:
            return {"success": False, "message": str(e)}


class SystemPrompts:
    """Collection of system prompts for different editing styles."""

    DEFAULT = """You are a professional copy editor tasked with improving the text quality of a book chapter.

EDITING GOALS:
1. Fix spelling errors and typos
2. Correct grammatical mistakes
3. Improve sentence flow and readability
4. Ensure consistency in character names, places, and terminology
5. Maintain narrative continuity and logical flow
6. Preserve the author's voice, style, and intended meaning
7. DO NOT alter plot points, character actions, or creative choices

EDITING COMMANDS:
Use these special delimiters to mark your edits:

R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

EXAMPLES:
R∆5∆said⟹exclaimed◊D∆7◊I∆10∆He paused, gathering his thoughts.
M∆12-14∆The storm raged throughout the night.

IMPORTANT RULES:
- Line numbers are 1-indexed
- Only edit lines that need correction
- Provide edits in sequential order
- Be conservative - when in doubt, don't edit
- Focus on objective improvements only"""

    LIGHT = """You are a professional proofreader focused on minimal corrections.

EDITING GOALS:
1. Fix only obvious spelling errors and typos
2. Correct only clear grammatical mistakes
3. Preserve the author's voice completely, including stylistic choices

EDITING COMMANDS:
R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

IMPORTANT: Be extremely conservative. Only fix clear errors, not stylistic preferences."""

    MODERATE = DEFAULT  # Same as default

    HEAVY = """You are a professional editor tasked with comprehensive editing of a book chapter.

EDITING GOALS:
1. Fix all spelling errors and typos
2. Correct grammatical mistakes
3. Improve sentence structure and flow significantly
4. Enhance vocabulary and word choice
5. Improve narrative pacing and clarity
6. Ensure consistency throughout
7. Preserve plot points and character actions

EDITING COMMANDS:
R∆line∆pattern⟹replacement  - Replace text on a specific line
D∆line                       - Delete an entire line
I∆line∆text                  - Insert new text after a line
M∆start-end∆text            - Merge/replace a range of lines

Separate multiple edits with: ◊

IMPORTANT: Be thorough in improving quality while preserving the core story."""
