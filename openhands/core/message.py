from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, Field, model_serializer
from typing_extensions import Literal

from openhands.core.logger import openhands_logger as logger


class ContentType(Enum):
    TEXT = 'text'
    IMAGE_URL = 'image_url'


class Content(BaseModel):
    type: str
    cache_prompt: bool = False

    @model_serializer
    def serialize_model(self):
        raise NotImplementedError('Subclasses should implement this method.')


class TextContent(Content):
    type: str = ContentType.TEXT.value
    text: str

    @model_serializer
    def serialize_model(self):
        data: dict[str, str | dict[str, str]] = {
            'type': self.type,
            'text': self.text,
        }
        if self.cache_prompt:
            data['cache_control'] = {'type': 'ephemeral'}
        return data


class ImageContent(Content):
    type: str = ContentType.IMAGE_URL.value
    image_urls: list[str]

    @model_serializer
    def serialize_model(self):
        images: list[dict[str, str | dict[str, str]]] = []
        for url in self.image_urls:
            images.append({'type': self.type, 'image_url': {'url': url}})
        if self.cache_prompt and images:
            images[-1]['cache_control'] = {'type': 'ephemeral'}
        return images


class Message(BaseModel):
    role: Literal['user', 'system', 'assistant']
    content: list[TextContent | ImageContent] = Field(default=list)

    @property
    def contains_image(self) -> bool:
        return any(isinstance(content, ImageContent) for content in self.content)

    @model_serializer
    def serialize_model(self) -> dict:
        content: list[dict[str, str | dict[str, str]]] = []

        for item in self.content:
            if isinstance(item, TextContent):
                content.append(item.model_dump())
            elif isinstance(item, ImageContent):
                content.extend(item.model_dump())

        return {'content': content, 'role': self.role}


def format_messages(
    messages: Union[Message, list[Message]], with_images: bool
) -> list[dict]:
    if not isinstance(messages, list):
        messages = [messages]

    if with_images:
        return [message.model_dump() for message in messages]

    converted_messages = []
    for message in messages:
        content_parts = []
        role = 'user'
        cache_prompt = False

        if isinstance(message, str) and message:
            content_parts.append(message)
        elif isinstance(message, dict):
            role = message.get('role', 'user')
            if 'content' in message and message['content']:
                content_parts.append(message['content'])
            cache_prompt = message.get('cache_prompt', False)
        elif isinstance(message, Message):
            role = message.role
            for content in message.content:
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, TextContent) and item.text:
                            content_parts.append(item.text)
                            cache_prompt |= item.cache_prompt
                elif isinstance(content, TextContent) and content.text:
                    content_parts.append(content.text)
                    cache_prompt |= content.cache_prompt
        else:
            logger.error(
                f'>>> `message` is not a string, dict, or Message: {type(message)}'
            )

        if content_parts:
            content_str = '\n'.join(content_parts)
            formatted_message: dict[str, Any] = {
                'role': role,
                'content': content_str,
            }
            if cache_prompt:
                formatted_message['cache_control'] = {'type': 'ephemeral'}
            converted_messages.append(formatted_message)

    return converted_messages
