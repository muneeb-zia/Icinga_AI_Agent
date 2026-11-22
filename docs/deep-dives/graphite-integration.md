# AI Engineering: Graphite Integration Breakdown

This document explains the Python logic and AI Engineering concepts we used to add Graphite visualization to the Icinga Agent. You can use this to understand *how* the AI interacts with APIs and dynamically generates UI elements.

## 1. Dynamic Tool Creation (`@tool`)
In `agent.py`, we created a new capability for the LLM using the `@tool` decorator. 

```python
@tool
def plot_historical_metrics(hostname: str, metric_name: str) -> str:
    """
    Plots the historical time-series data for a specific metric and returns a visual graph.
    Use this when the user asks to 'show me the trend', 'plot the cpu', 'visualize the past data', etc.
    """
```
**Why this matters:** The docstring (`"""..."""`) is incredibly important. The LLM reads this text to decide *when* to use the tool. If the user types "plot the cpu", the LLM matches the word "plot" to the docstring and executes this Python function.

## 2. In-Memory Image Generation (The "Base64 Trick")
Streamlit is great, but getting an LLM to tell Streamlit to draw a graph can be tricky. Instead, we have the Python tool draw the graph itself using `matplotlib`, save it to memory (RAM), and encode it as text (Base64).

```python
import io
import base64
import matplotlib.pyplot as plt

# 1. Create a buffer in RAM (instead of saving to hard drive)
buf = io.BytesIO()

# 2. Draw the plot and save it into the RAM buffer
plt.savefig(buf, format='png')
buf.seek(0)

# 3. Convert the binary image data into a long string of text (Base64)
image_base64 = base64.b64encode(buf.read()).decode('utf-8')

# 4. Return it as a Markdown image!
return f"![Historical Trend](data:image/png;base64,{image_base64})"
```
**Why this matters:** LLMs can only output text. By converting an image into a Base64 Markdown string, the LLM can output a "text" response that Streamlit instantly renders as a beautiful visual graph. This avoids dealing with file paths, permissions, or complex UI callbacks.

## Summary
By combining **Robust Error Handling**, **Clear Tool Docstrings**, and **Base64 Image Encoding**, we successfully gave the AI agent a brand new visual capability without touching the main UI (`app.py`) or breaking the existing Phase 1 read-only features. The agent is fully capable of fetching real data and gracefully reporting errors (like connection timeouts) when Graphite is inaccessible. Once you receive the real Graphite API URL, simply update `GRAPHITE_URL` in `graphite_api.py` and the visualizations will be live.
