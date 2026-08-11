import os
import agent
import base64

def test_visualization():
    print("Running visualization test with demo data...")
    
    # Call the tool directly just like the LLM would
    result_markdown = agent.plot_historical_metrics.invoke({"hostname": "master-node", "metric_name": "cpu"})
    
    if "error" in result_markdown.lower() or "could not fetch" in result_markdown.lower():
        print(f"Error occurred: {result_markdown}")
        return

    # Extract the base64 string from the markdown
    # Format is ![Alt](data:image/png;base64,DATA)
    try:
        base64_data = result_markdown.split("base64,")[1].split(")")[0]
        image_data = base64.b64decode(base64_data)
        
        output_file = "demo_visualization.png"
        with open(output_file, "wb") as f:
            f.write(image_data)
            
        print(f"SUCCESS! Visualization generated and saved to {os.path.abspath(output_file)}")
        print("\nYou can open this image file to see what the Streamlit UI would render.")
    except Exception as e:
        print(f"Failed to extract and save image: {e}")

if __name__ == "__main__":
    test_visualization()
