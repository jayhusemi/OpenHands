import warnings
from functools import partial

import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import litellm
from litellm import completion as litellm_completion
from litellm import completion_cost as litellm_completion_cost
from litellm import embedding as litellm_embedding
from litellm.exceptions import (
    APIConnectionError,
    RateLimitError,
    ServiceUnavailableError,
)
from litellm.types.utils import CostPerToken
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from opendevin.core.config import config
from opendevin.core.logger import llm_prompt_logger, llm_response_logger
from opendevin.core.logger import opendevin_logger as logger
from opendevin.core.metrics import Metrics

__all__ = ['LLM']

message_separator = '\n\n----------\n\n'


class LLM:
    """
    The LLM class represents a Language Model instance.

    Attributes:
        model_name (str): The name of the language model.
        api_key (str): The API key for accessing the language model.
        base_url (str): The base URL for the language model API.
        api_version (str): The version of the API to use.
        max_input_tokens (int): The maximum number of tokens to send to the LLM per task.
        max_output_tokens (int): The maximum number of tokens to receive from the LLM per task.
        llm_timeout (int): The maximum time to wait for a response in seconds.
        custom_llm_provider (str): A custom LLM provider.
    """

    def __init__(
        self,
        model=None,
        api_key=None,
        base_url=None,
        api_version=None,
        num_retries=None,
        retry_min_wait=None,
        retry_max_wait=None,
        llm_timeout=None,
        llm_temperature=None,
        llm_top_p=None,
        custom_llm_provider=None,
        max_input_tokens=None,
        max_output_tokens=None,
        llm_config=None,
        metrics=None,
        cost_metric_supported=True,
    ):
        """
        Initializes the LLM. If LLMConfig is passed, its values will be the fallback.

        Passing simple parameters always overrides config.

        Args:
            model (str, optional): The name of the language model. Defaults to LLM_MODEL.
            api_key (str, optional): The API key for accessing the language model. Defaults to LLM_API_KEY.
            base_url (str, optional): The base URL for the language model API. Defaults to LLM_BASE_URL. Not necessary for OpenAI.
            api_version (str, optional): The version of the API to use. Defaults to LLM_API_VERSION. Not necessary for OpenAI.
            num_retries (int, optional): The number of retries for API calls. Defaults to LLM_NUM_RETRIES.
            retry_min_wait (int, optional): The minimum time to wait between retries in seconds. Defaults to LLM_RETRY_MIN_TIME.
            retry_max_wait (int, optional): The maximum time to wait between retries in seconds. Defaults to LLM_RETRY_MAX_TIME.
            max_input_tokens (int, optional): The maximum number of tokens to send to the LLM per task. Defaults to LLM_MAX_INPUT_TOKENS.
            max_output_tokens (int, optional): The maximum number of tokens to receive from the LLM per task. Defaults to LLM_MAX_OUTPUT_TOKENS.
            custom_llm_provider (str, optional): A custom LLM provider. Defaults to LLM_CUSTOM_LLM_PROVIDER.
            llm_timeout (int, optional): The maximum time to wait for a response in seconds. Defaults to LLM_TIMEOUT.
            llm_temperature (float, optional): The temperature for LLM sampling. Defaults to LLM_TEMPERATURE.
            metrics (Metrics, optional): The metrics object to use. Defaults to None.
            cost_metric_supported (bool, optional): Whether the cost metric is supported. Defaults to True.
        """
        if llm_config is None:
            llm_config = config.llm
        model = model if model is not None else llm_config.model
        api_key = api_key if api_key is not None else llm_config.api_key
        base_url = base_url if base_url is not None else llm_config.base_url
        api_version = api_version if api_version is not None else llm_config.api_version
        num_retries = num_retries if num_retries is not None else llm_config.num_retries
        retry_min_wait = (
            retry_min_wait if retry_min_wait is not None else llm_config.retry_min_wait
        )
        retry_max_wait = (
            retry_max_wait if retry_max_wait is not None else llm_config.retry_max_wait
        )
        llm_timeout = llm_timeout if llm_timeout is not None else llm_config.timeout
        llm_temperature = (
            llm_temperature if llm_temperature is not None else llm_config.temperature
        )
        llm_top_p = llm_top_p if llm_top_p is not None else llm_config.top_p
        custom_llm_provider = (
            custom_llm_provider
            if custom_llm_provider is not None
            else llm_config.custom_llm_provider
        )
        max_input_tokens = (
            max_input_tokens
            if max_input_tokens is not None
            else llm_config.max_input_tokens
        )
        max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else llm_config.max_output_tokens
        )
        metrics = metrics if metrics is not None else Metrics()

        logger.info(f'Initializing LLM with model: {model}')
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.llm_timeout = llm_timeout
        self.custom_llm_provider = custom_llm_provider
        self.metrics = metrics
        self.cost_metric_supported = cost_metric_supported

        # assert temperature > 0.0 when agent_action_best_of_n is set
        self.agent_action_best_of_n = llm_config.agent_action_best_of_n
        assert (
            llm_temperature > 0.0
        ), 'Temperature must be greater than 0.0 when agent_action_best_of_n is set'
        if self.agent_action_best_of_n is not None:
            logger.info(
                f'Agent action BEST of N is enabled: {self.agent_action_best_of_n}'
            )

        # litellm actually uses base Exception here for unknown model
        self.model_info = None
        try:
            if not self.model_name.startswith('openrouter'):
                self.model_info = litellm.get_model_info(self.model_name.split(':')[0])
            else:
                self.model_info = litellm.get_model_info(self.model_name)
        # noinspection PyBroadException
        except Exception:
            logger.warning(f'Could not get model info for {self.model_name}')

        if self.max_input_tokens is None:
            if self.model_info is not None and 'max_input_tokens' in self.model_info:
                self.max_input_tokens = self.model_info['max_input_tokens']
            else:
                # Max input tokens for gpt3.5, so this is a safe fallback for any potentially viable model
                self.max_input_tokens = 4096

        if self.max_output_tokens is None:
            if self.model_info is not None and 'max_output_tokens' in self.model_info:
                self.max_output_tokens = self.model_info['max_output_tokens']
            else:
                # Enough tokens for most output actions, and not too many for a bad llm to get carried away responding
                # with thousands of unwanted tokens
                self.max_output_tokens = 1024

        self._completion = partial(
            litellm_completion,
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            custom_llm_provider=custom_llm_provider,
            max_tokens=self.max_output_tokens,
            timeout=self.llm_timeout,
            temperature=llm_temperature,
            top_p=llm_top_p,
        )

        completion_unwrapped = self._completion

        def attempt_on_error(retry_state):
            logger.error(
                f'{retry_state.outcome.exception()}. Attempt #{retry_state.attempt_number} | You can customize these settings in the configuration.',
                exc_info=False,
            )
            return True

        @retry(
            reraise=True,
            stop=stop_after_attempt(num_retries),
            wait=wait_random_exponential(min=retry_min_wait, max=retry_max_wait),
            retry=retry_if_exception_type(
                (RateLimitError, APIConnectionError, ServiceUnavailableError)
            ),
            after=attempt_on_error,
        )
        def wrapper(*args, **kwargs):
            """
            Wrapper for the litellm completion function. Logs the input and output of the completion function.
            """

            # some callers might just send the messages directly
            if 'messages' in kwargs:
                messages = kwargs['messages']
            else:
                messages = args[1]

            # log the prompt
            debug_message = ''
            for message in messages:
                debug_message += message_separator + message['content']
            llm_prompt_logger.debug(debug_message)

            # call the completion function
            if kwargs.get('sample_action', True):
                kwargs.pop('sample_action')
                resp = self.perform_action_sampling(
                    completion_unwrapped, *args, **kwargs
                )
            else:
                resp = completion_unwrapped(*args, **kwargs)

            # log the response
            if len(resp['choices']) > 1:
                for choice in resp['choices']:
                    if choice['is_best_action']:
                        message_back = choice['message']['content']
                        break
            else:
                message_back = resp['choices'][0]['message']['content']
            llm_response_logger.debug(message_back)

            # post-process to log costs
            self._post_completion(resp)
            return resp

        self._completion = wrapper  # type: ignore

    @property
    def completion(self):
        """
        Decorator for the litellm completion function.

        Check the complete documentation at https://litellm.vercel.app/docs/completion
        """
        return self._completion

    def perform_action_sampling(self, completion_unwrapped, *args, **kwargs):
        """
        Perform action sampling.
        """
        # get the number of actions to sample
        num_actions = self.agent_action_best_of_n

        # sample num_actions actions
        kwargs['n'] = num_actions
        response = completion_unwrapped(*args, **kwargs)

        # iterate over the choices and get the action
        action_contents = []
        for choice in response['choices']:
            action_contents.append(choice['message']['content'])

        action_embeddings_response = litellm_embedding(
            model=config.llm.embedding_model,
            input=action_contents,
            custom_llm_provider=self.custom_llm_provider,
            api_key=self.api_key,
            base_url=self.base_url,
            api_version=self.api_version,
            input_cost_per_token=config.llm.input_cost_per_token,
            output_cost_per_token=config.llm.output_cost_per_token,
        )
        # calculate similarity between action embeddings
        action_embeddings = action_embeddings_response['data']
        # put into a matrix
        action_embeddings_mat = np.array([i['embedding'] for i in action_embeddings])
        # calculate similarity between action embeddings
        action_similarity_mat = np.dot(action_embeddings_mat, action_embeddings_mat.T)
        # Calculate average similarity for each action
        avg_similarities = np.mean(action_similarity_mat, axis=1)

        logger.info(f'{len(action_similarity_mat)} actions sampled.')
        logger.info(
            f'Action similarities (mean={np.mean(avg_similarities)}, std={np.std(avg_similarities)}): {avg_similarities}'
        )

        # Find the index of the action with the highest average similarity
        best_action_index = np.argmax(avg_similarities)

        for i, choice in enumerate(response['choices']):
            choice['avg_similarity'] = avg_similarities[i]
            if i == best_action_index:
                choice['is_best_action'] = True
            else:
                choice['is_best_action'] = False

        return response

    def _post_completion(self, response: str) -> None:
        """
        Post-process the completion response.
        """
        try:
            cur_cost = self.completion_cost(response)
        except Exception:
            cur_cost = 0
        if self.cost_metric_supported:
            logger.info(
                'Cost: %.2f USD | Accumulated Cost: %.2f USD',
                cur_cost,
                self.metrics.accumulated_cost,
            )

    def get_token_count(self, messages):
        """
        Get the number of tokens in a list of messages.

        Args:
            messages (list): A list of messages.

        Returns:
            int: The number of tokens.
        """
        return litellm.token_counter(model=self.model_name, messages=messages)

    def is_local(self):
        """
        Determines if the system is using a locally running LLM.

        Returns:
            boolean: True if executing a local model.
        """
        if self.base_url is not None:
            for substring in ['localhost', '127.0.0.1' '0.0.0.0']:
                if substring in self.base_url:
                    return True
        elif self.model_name is not None:
            if self.model_name.startswith('ollama'):
                return True
        return False

    def completion_cost(self, response):
        """
        Calculate the cost of a completion response based on the model.  Local models are treated as free.
        Add the current cost into total cost in metrics.

        Args:
            response (list): A response from a model invocation.

        Returns:
            number: The cost of the response.
        """
        if not self.cost_metric_supported:
            return 0.0

        extra_kwargs = {}
        if (
            config.llm.input_cost_per_token is not None
            and config.llm.output_cost_per_token is not None
        ):
            cost_per_token = CostPerToken(
                input_cost_per_token=config.llm.input_cost_per_token,
                output_cost_per_token=config.llm.output_cost_per_token,
            )
            logger.info(f'Using custom cost per token: {cost_per_token}')
            extra_kwargs['custom_cost_per_token'] = cost_per_token

        if not self.is_local():
            try:
                cost = litellm_completion_cost(
                    completion_response=response, **extra_kwargs
                )
                self.metrics.add_cost(cost)
                return cost
            except Exception:
                self.cost_metric_supported = False
                logger.warning('Cost calculation not supported for this model.')
        return 0.0

    def __str__(self):
        if self.api_version:
            return f'LLM(model={self.model_name}, api_version={self.api_version}, base_url={self.base_url})'
        elif self.base_url:
            return f'LLM(model={self.model_name}, base_url={self.base_url})'
        return f'LLM(model={self.model_name})'

    def __repr__(self):
        return str(self)
