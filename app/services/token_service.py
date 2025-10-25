"""Token counting service."""
import tiktoken
from typing import List, Dict
from app.config import settings


class TokenService:
    """Service for counting tokens using tiktoken."""

    def __init__(self, model: str = "gpt-4"):
        """
        Initialize token service.

        Args:
            model: Model name for encoding (e.g., 'gpt-4', 'gpt-3.5-turbo')
        """
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Default to cl100k_base encoding (used by GPT-4 and GPT-3.5-turbo)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def count_message_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Count tokens in a list of messages (ChatML format).

        Args:
            messages: List of message dictionaries with 'role' and 'content'

        Returns:
            Total number of tokens
        """
        tokens = 0

        for message in messages:
            # Add tokens for message structure
            tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n

            for key, value in message.items():
                tokens += self.count_tokens(str(value))

                if key == "name":  # If there's a name, the role is omitted
                    tokens += -1  # Role is always required and always 1 token

        tokens += 2  # Every reply is primed with <im_start>assistant

        return tokens

    @staticmethod
    def calculate_batch_groups(
        chapters: List[Dict],
        max_tokens: int,
        system_prompt: str,
        model: str = "gpt-4",
    ) -> List[List[Dict]]:
        """
        Group chapters to maximize token usage while staying under limits.

        Args:
            chapters: List of chapter dictionaries with 'token_count' field
            max_tokens: Maximum tokens allowed per request
            system_prompt: The system prompt text
            model: Model name for token counting

        Returns:
            List of chapter batches
        """
        token_service = TokenService(model)

        # Calculate system prompt tokens
        system_prompt_tokens = token_service.count_tokens(system_prompt)

        # Reserve space for response and message structure
        available_tokens = max_tokens - system_prompt_tokens - settings.safety_buffer

        batches = []
        current_batch = []
        current_tokens = 0

        for chapter in chapters:
            chapter_tokens = chapter.get("token_count", 0)

            # Check if single chapter exceeds limit
            if chapter_tokens > available_tokens:
                # This chapter needs to be split or processed alone
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                batches.append([chapter])
                continue

            # Try to add to current batch
            if current_tokens + chapter_tokens <= available_tokens:
                current_batch.append(chapter)
                current_tokens += chapter_tokens
            else:
                # Start new batch
                if current_batch:
                    batches.append(current_batch)

                current_batch = [chapter]
                current_tokens = chapter_tokens

        # Add remaining batch
        if current_batch:
            batches.append(current_batch)

        return batches

    @staticmethod
    def estimate_cost(
        input_tokens: int,
        output_tokens: int,
        model: str = "gpt-4",
    ) -> float:
        """
        Estimate API cost based on token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        # Pricing as of 2024 (adjust as needed)
        pricing = {
            "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
            "gpt-4-turbo": {"input": 0.01 / 1000, "output": 0.03 / 1000},
            "gpt-3.5-turbo": {"input": 0.0005 / 1000, "output": 0.0015 / 1000},
            "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
            "gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.0006 / 1000},
        }

        # Default to gpt-4 pricing if model not found
        model_pricing = pricing.get(model, pricing["gpt-4"])

        input_cost = input_tokens * model_pricing["input"]
        output_cost = output_tokens * model_pricing["output"]

        return input_cost + output_cost
