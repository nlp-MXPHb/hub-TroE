import os
import sys

# Flat src/ layout: bare module imports (config, models, tools.web_search, ...).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
