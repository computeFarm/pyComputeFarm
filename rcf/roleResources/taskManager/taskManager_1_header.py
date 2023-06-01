"""
Manage a collection of specialized task workers by assigning new tasks
in a simple round-robin fashion using one asyncio Queue for each
specialized task.

Echoing the results from the assigned worker back to the requester.

"""

import asyncio
import json
import random
import signal
import sys
import time
import traceback
import yaml

