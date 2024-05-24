#!/bin/bash

set -e

# add agent_skills to PATH
echo 'export PATH=/opendevin/plugins/agent_skills:$PATH' >> ~/.bashrc
export PATH=/opendevin/plugins/agent_skills:$PATH

# add agent_skills to PYTHONPATH
echo 'export PYTHONPATH=/opendevin/plugins/agent_skills:$PYTHONPATH' >> ~/.bashrc
export PYTHONPATH=/opendevin/plugins/agent_skills:$PYTHONPATH

pip install flake8 openai python-docx PyPDF2 openpyxl pylatexenc python-pptx requests opencv-python pandas