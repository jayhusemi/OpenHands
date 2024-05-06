from enum import Enum


class ConfigType(str, Enum):
    LLM_TOP_P = 'LLM_TOP_P'
    LLM_TEMPERATURE = 'LLM_TEMPERATURE'
    LLM_MAX_RETURN_TOKENS = 'LLM_MAX_RETURN_TOKENS'
    LLM_TIMEOUT = 'LLM_TIMEOUT'
    LLM_API_KEY = 'LLM_API_KEY'
    LLM_BASE_URL = 'LLM_BASE_URL'
    WORKSPACE_BASE = 'WORKSPACE_BASE'
    WORKSPACE_MOUNT_PATH = 'WORKSPACE_MOUNT_PATH'
    WORKSPACE_MOUNT_REWRITE = 'WORKSPACE_MOUNT_REWRITE'
    WORKSPACE_MOUNT_PATH_IN_SANDBOX = 'WORKSPACE_MOUNT_PATH_IN_SANDBOX'
    CACHE_DIR = 'CACHE_DIR'
    LLM_MODEL = 'LLM_MODEL'
    SANDBOX_CONTAINER_IMAGE = 'SANDBOX_CONTAINER_IMAGE'
    RUN_AS_DEVIN = 'RUN_AS_DEVIN'
    LLM_EMBEDDING_MODEL = 'LLM_EMBEDDING_MODEL'
    LLM_EMBEDDING_BASE_URL = 'LLM_EMBEDDING_BASE_URL'
    LLM_EMBEDDING_DEPLOYMENT_NAME = 'LLM_EMBEDDING_DEPLOYMENT_NAME'
    LLM_API_VERSION = 'LLM_API_VERSION'
    LLM_NUM_RETRIES = 'LLM_NUM_RETRIES'
    LLM_RETRY_MIN_WAIT = 'LLM_RETRY_MIN_WAIT'
    LLM_RETRY_MAX_WAIT = 'LLM_RETRY_MAX_WAIT'
    AGENT_MEMORY_MAX_THREADS = 'AGENT_MEMORY_MAX_THREADS'
    AGENT_MEMORY_ENABLED = 'AGENT_MEMORY_ENABLED'
    MAX_ITERATIONS = 'MAX_ITERATIONS'
    MAX_CHARS = 'MAX_CHARS'
    AGENT = 'AGENT'
    E2B_API_KEY = 'E2B_API_KEY'
    SANDBOX_TYPE = 'SANDBOX_TYPE'
    SANDBOX_USER_ID = 'SANDBOX_USER_ID'
    SANDBOX_TIMEOUT = 'SANDBOX_TIMEOUT'
    USE_HOST_NETWORK = 'USE_HOST_NETWORK'
    SSH_HOSTNAME = 'SSH_HOSTNAME'
    DISABLE_COLOR = 'DISABLE_COLOR'
    GITHUB_TOKEN = 'GITHUB_TOKEN'
    DEBUG = 'DEBUG'
