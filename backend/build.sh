#!/bin/bash
pip install --upgrade pip
pip install -r requirements.txt
pip install websockets==12.0
python -m playwright install chromium
