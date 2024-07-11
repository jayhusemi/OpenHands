#!/bin/bash
set -eo pipefail

source "evaluation/utils/version_control.sh"

MODEL_CONFIG=$1
COMMIT_HASH=$2
AGENT=$3
EVAL_LIMIT=$4
LEVELS=$5
NUM_WORKERS=$6

if [ -z "$NUM_WORKERS" ]; then
  NUM_WORKERS=1
  echo "Number of workers not specified, use default $NUM_WORKERS"
fi
checkout_eval_branch

if [ -z "$AGENT" ]; then
  echo "Agent not specified, use default GPTSwarmAgent"
  AGENT="GPTSwarmAgent"
fi

get_agent_version

if [ -z "$LEVELS" ]; then
  LEVELS="2023_level1"
  echo "Levels not specified, use default $LEVELS"
fi

get_agent_version

echo "AGENT: $AGENT"
echo "AGENT_VERSION: $AGENT_VERSION"
echo "MODEL_CONFIG: $MODEL_CONFIG"
echo "LEVELS: $LEVELS"

COMMAND="poetry run python ./evaluation/gaia/run_infer.py \
  --agent-cls $AGENT \
  --llm-config $MODEL_CONFIG \
  --level $LEVELS \
  --data-split validation"

if [ -n "$EVAL_LIMIT" ]; then
  echo "EVAL_LIMIT: $EVAL_LIMIT"
  COMMAND="$COMMAND --eval-n-limit $EVAL_LIMIT"
fi

# Run the command
eval $COMMAND
