from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from openhands.core.logger import openhands_logger as logger
from openhands.runtime.base import Runtime

app = APIRouter(prefix='/api')


@app.get('/conversation')
async def get_remote_runtime_config(request: Request):
    """Retrieve the runtime configuration.

    Currently, this is the session ID and runtime ID (if available).
    """
    runtime = request.state.conversation.runtime
    runtime_id = runtime.runtime_id if hasattr(runtime, 'runtime_id') else None
    session_id = runtime.sid if hasattr(runtime, 'sid') else None
    return JSONResponse(
        content={
            'runtime_id': runtime_id,
            'session_id': session_id,
        }
    )


@app.get('/vscode-url')
async def get_vscode_url(request: Request):
    """Get the VSCode URL.

    This endpoint allows getting the VSCode URL.

    Args:
        request (Request): The incoming FastAPI request object.

    Returns:
        JSONResponse: A JSON response indicating the success of the operation.
    """
    try:
        runtime: Runtime = request.state.conversation.runtime
        logger.debug(f'Runtime type: {type(runtime)}')
        logger.debug(f'Runtime VSCode URL: {runtime.vscode_url}')
        return JSONResponse(status_code=200, content={'vscode_url': runtime.vscode_url})
    except Exception as e:
        logger.error(f'Error getting VSCode URL: {e}', exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                'vscode_url': None,
                'error': f'Error getting VSCode URL: {e}',
            },
        )
