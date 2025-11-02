import os
import json
from flask import Flask, request as flask_request, jsonify
from flask_cors import CORS
from base64 import b64decode
from google.cloud import storage 
from google import genai
from google.genai import types

# --- 1. CONFIGURATION ---
# NOTE: Using an environment variable for GCS_BUCKET_NAME is recommended, but hardcoding is left as per your original code.
GCS_BUCKET_NAME = "hackathon-cement-plant-image-data"
KILN_GCS_PREFIX = "kiln/" 

# Fuel rate operating range for the natural language recommendation
FUEL_RATE_NORMAL_MIN = 9.2
FUEL_RATE_NORMAL_MAX = 9.8
FUEL_RATE_VARIABLE = "fuel_feed_rate_tph"

# --- 2. GLOBAL INITIALIZATION ---
storage_client = storage.Client()
_gemini_client = None

def get_gemini_client():
    """Initializes the Gemini client, prioritizing an API key from the environment 
    or falling back to the Vertex AI configuration."""
    global _gemini_client
    if _gemini_client is None:
        print("Attempting to initialize Gemini Client...")
        
        API_KEY = os.environ.get('GEMINI_API_KEY')
        
        if API_KEY:
            _gemini_client = genai.Client(api_key=API_KEY)
            print("Gemini Client initialized using explicit API Key.")
        else:
            # Fallback to Vertex AI context (using environment variable for PROJECT_ID)
            PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT') 
            
            _gemini_client = genai.Client(vertexai=True,
                project=PROJECT_ID,
                location='us-central1'
            )
            print(f"Gemini Client initialized for Vertex AI Project: {PROJECT_ID}")
            
    return _gemini_client

# Initialize the Flask application
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# -----------------------------------------------------------------------------

# --- 3. GCS UTILITY FUNCTION ---

def get_gcs_image_uris(bucket_name: str, prefix: str) -> list[str]:
    """Lists all image URIs in the specified GCS bucket and prefix."""
    
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs(prefix=prefix)
    
    uris = [
        f"gs://{bucket_name}/{blob.name}" 
        for blob in blobs 
        if blob.name != prefix and blob.name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ]
    
    if not uris:
        raise ValueError(f"No few-shot images found in gs://{bucket_name}/{prefix}. Please verify images and path.")
        
    return sorted(uris)

# -----------------------------------------------------------------------------

# --- 4. PROMPT CONSTRUCTION LOGIC (OPTIMIZED FOR DYNAMIC RESPONSE) ---

def get_target_json(uri: str):
    """Determines the target JSON based on the image file name/path."""
    
    KPI_FOCUS = "kiln_specific_thermal_energy_Kcal/kg_clinker"
    
    if "kiln_operating_normal" in uri:
        return {
            "recommendation_type": "KILN_SETPOINT_ADJUSTMENT",
            "kpi_focus": KPI_FOCUS,
            "visual_finding": "Stable flame, optimal combustion, normal shell temperature distribution.",
            "severity_level": "low", 
            "adjustments": [{"variable": FUEL_RATE_VARIABLE, "action": "MAINTAIN", "value": 0.0}],
            "recommendation": f"The kiln appears to be operating optimally. Continue maintaining the {FUEL_RATE_VARIABLE} between {FUEL_RATE_NORMAL_MIN} and {FUEL_RATE_NORMAL_MAX} tph."
        }
    elif "kiln_overheating_anomaly_high" in uri:
        return {
            "recommendation_type": "CRITICAL_ALERT",
            "kpi_focus": KPI_FOCUS,
            "visual_finding": "Severe, extensive overheating anomaly (large red glowing areas on the shell). High risk of immediate refractory failure and shell damage.",
            "severity_level": "high",
            "adjustments": [{"variable": FUEL_RATE_VARIABLE, "action": "DECREASE", "value": 0.3}],
            "recommendation": f"CRITICAL ALERT: Extensive overheating detected. Immediately decrease the {FUEL_RATE_VARIABLE} by 0.3 tph to prevent catastrophic damage."
        }
    elif "kiln_overheating_anomaly_medium" in uri:
        return {
            "recommendation_type": "WARNING",
            "kpi_focus": KPI_FOCUS,
            "visual_finding": "Medium overheating anomaly (isolated, bright red spots on shell). Potential for localized refractory wear.",
            "severity_level": "medium",
            "adjustments": [{"variable": FUEL_RATE_VARIABLE, "action": "DECREASE", "value": 0.2}],
            "recommendation": f"WARNING: Isolated thermal deviation detected. Reduce the {FUEL_RATE_VARIABLE} by 0.2 tph and monitor closely for stabilization."
        }
    else:
        # Default or unclassified medium case
        return {
            "recommendation_type": "WARNING",
            "kpi_focus": KPI_FOCUS,
            "visual_finding": f"Unclassified thermal deviation: {os.path.basename(uri)}. Requires cautious adjustment.",
            "severity_level": "medium",
            "adjustments": [{"variable": FUEL_RATE_VARIABLE, "action": "DECREASE", "value": 0.2}],
            "recommendation": f"Unclassified visual anomaly detected. As a cautious measure, decrease the {FUEL_RATE_VARIABLE} by 0.2 tph to stabilize the process."
        }


def create_kiln_prompt(test_image_b64: str, test_image_mimetype: str) -> tuple[list, str]:
    """
    Constructs the full list of contents and returns the system instruction.
    """
    
    system_instruction = (
        "You are the autonomous Kiln Controller. Analyze the attached images to predict the kiln's thermal efficiency. "
        "Your primary objective is to minimize 'kiln_specific_thermal_energy_Kcal/kg_clinker' by recommending immediate adjustments. "
        "The standard operating range for the fuel feed rate is 9.2 - 9.8 tph. "
        "Output MUST be a single JSON object matching the schema shown in the examples."
        "\n\n--- DYNAMIC LOGIC RULES ---"
        "\n1. Severity Level: Classify the thermal state into 'low' (normal/minor), 'medium' (deviation/warning), or 'high' (critical/severe)."
        "\n2. Adjustment Value (Dynamic):"
        f"\n  - If action is 'DECREASE' and severity is 'low', set 'value' to 0.1."
        f"\n  - If action is 'DECREASE' and severity is 'medium', set 'value' to 0.2."
        f"\n  - If action is 'DECREASE' and severity is 'high', set 'value' to 0.3."
        "\n  - If action is 'MAINTAIN', 'value' MUST be 0.0."
        "\n3. Recommendation Key: Generate a **unique, non-repetitive** natural language explanation (1-2 sentences) of the visual finding and the prescribed corrective action. The tone should be authoritative and informative. Reference the fuel feed rate range (9.2 - 9.8 tph) when the action is MAINTAIN."
    )
    
    contents = [] 
    
    try:
        KILN_FEW_SHOT_URIS = get_gcs_image_uris(GCS_BUCKET_NAME, KILN_GCS_PREFIX)
    except ValueError as e:
        raise e
    
    # 2. Add few-shot examples (user query + model response)
    for i, uri in enumerate(KILN_FEW_SHOT_URIS):
        target_json = get_target_json(uri)
        
        # User query (text + image URI)
        text_part = types.Part(text=f"EXAMPLE {i+1}: Analyze this image at {uri}")
        
        # Using explicit types.FileData inside types.Part for GCS URIs
        uri_part = types.Part(
            file_data=types.FileData(
                file_uri=uri,
                mime_type="image/jpeg", 
            )
        )
        
        # Append the User Content
        contents.append(
            types.Content(role="user", parts=[text_part, uri_part])
        )
        
        # Model response (JSON text)
        json_part = types.Part(text=json.dumps(target_json))
        
        # Append the Model Content
        contents.append(
            types.Content(role="model", parts=[json_part])
        )

    # 3. Add the final live image task (text + image bytes)
    live_image_bytes = b64decode(test_image_b64)
    
    final_text_part = types.Part(text="FINAL TASK: Analyze this current live image and provide the required JSON recommendation, strictly following the specified DYNAMIC LOGIC RULES.")
    
    final_image_part = types.Part.from_bytes(data=live_image_bytes, mime_type=test_image_mimetype)
    
    contents.append(
        types.Content(role="user", parts=[final_text_part, final_image_part])
    )
    
    return contents, system_instruction

# -----------------------------------------------------------------------------

# --- 5. MAIN ENTRY POINT HANDLER ---

def flask_predict(request_param=None):
    """
    Handles the main POST request for image analysis, including CORS preflight.
    """
    # Handle CORS preflight request
    if flask_request.method == 'OPTIONS':
        response = app.response_class(
            response='',
            status=204, 
            mimetype='text/plain'
        )
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        request_json = flask_request.get_json(silent=True) 

        if not request_json:
            raise ValueError("Invalid JSON or empty request body.")

        if 'image_data_b64' not in request_json:
            raise KeyError("Missing required key 'image_data_b64' in the JSON payload.")

        test_image_b64 = request_json['image_data_b64']
        test_image_mimetype = request_json.get('mime_type', 'image/jpeg')
        
        gemini_client = get_gemini_client()

        prompt_contents, system_instruction = create_kiln_prompt(test_image_b64, test_image_mimetype)

        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction, 
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        
        flask_response = app.response_class(
            response=response.text,
            status=200,
            mimetype='application/json'
        )
        flask_response.headers.add('Access-Control-Allow-Origin', '*')
        return flask_response

    except Exception as e:
        print(f"Error processing request: {e}")
        error_response = jsonify({"error": str(e)})
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 500

# -----------------------------------------------------------------------------

# --- 6. FLASK ROUTES ---

@app.route('/', methods=['POST', 'OPTIONS'])
def flask_route():
    return flask_predict()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

# --- 7. STANDALONE SERVER STARTUP ---

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)