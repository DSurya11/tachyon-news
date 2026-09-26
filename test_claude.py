import logging
from datetime import date
from pipeline.report.claude_web import generate_report

logging.basicConfig(level=logging.INFO)

# Dummy prompt to test it
prompt = "Hello Claude, this is a test from the stock news pipeline. Just say 'TEST SUCCESSFUL' if you get this."
generate_report(date.today(), prompt, [])
