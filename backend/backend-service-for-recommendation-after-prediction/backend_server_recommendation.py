import os
import json
from flask import Flask, request as flask_request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

# --- 1. CONFIGURATION (Core Constants) ---

# Target KPI Constraints
FREE_LIME_TARGET_MAX = 1.2  # Max acceptable clinker free lime %
THERMAL_ENERGY_TARGET_MIN = 750.0  # Soft target/lower bound for thermal energy

# Controllable Variable Operating Ranges
CONTROLLABLE_RANGES = {
    # 5 Blending Inputs
    "raw_meal_lsf_ratio": "92.0 - 98.0 Ratio (Primary quality lever, lagged 5h)",
    "limestone_feed_rate_pct": "76.0 - 80.0 % (Typical: ~78%. Composition control.)", 
    "clay_feed_rate_pct": "14.0 - 18.0 % (Typical: ~16%. Composition control.)",
    "iron_ore_feed_rate_pct": "3.0 - 4.0 % (Typical: ~3.5%. Composition control.)",
    "bauxite_feed_rate_pct": "2.0 - 3.0 % (Typical: ~2.5%. Composition control.)",
    # 6 Pyroprocessing Inputs
    "raw_meal_feed_rate_tph": "170.0 - 180.0 tph (Overall production rate)",
    "fuel_feed_rate_tph": "9.2 - 9.8 tph (Primary control for Thermal Energy)",
    "fuel_alt_substitution_rate_pct": "15.0 - 25.0 % (Efficiency control)",
    "kiln_hood_pressure_mmH2O": "-7.0 to -5.0 mmH2O (Air control, inverse sign)",
    "kiln_burner_air_flow_m3/hr": "24000.0 - 26000.0 m3/hr (Combustion control)",
    "kiln_main_drive_current_Amp": "190.0 - 210.0 Amp (Used for stabilization/load balance.)", 
}

# --- 2. GLOBAL INITIALIZATION ---
_gemini_client = None

def get_gemini_client():
    """
    Initializes the Gemini client, prioritizing an API key from the environment 
    or falling back to the Vertex AI configuration (best for Cloud Run/Functions).
    """
    global _gemini_client
    if _gemini_client is None:
        print("Attempting to initialize Gemini Client...")
        
        API_KEY = os.environ.get('GEMINI_API_KEY')
        
        if API_KEY:
            _gemini_client = genai.Client(api_key=API_KEY)
            print("Gemini Client initialized using explicit API Key.")
        else:
            # Fallback to Vertex AI context, relying on the environment to set GOOGLE_CLOUD_PROJECT
            PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT')
            
            _gemini_client = genai.Client(
                vertexai=True,
                project=PROJECT_ID,
                location='us-central1'
            )
            print(f"Gemini Client initialized for Vertex AI Project: {PROJECT_ID}")
            
    return _gemini_client

# Initialize the Flask application
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# -----------------------------------------------------------------------------

# --- 3. CORE LLM-DRIVEN LOGIC ---

def generate_recommendations_llm(current_inputs: dict, predicted_kpis: dict) -> list[dict]:
    """
    Calls the Gemini model to generate prescriptive recommendations.
    """
    
    # 1. Define the complete system instruction and context
    SYSTEM_INSTRUCTION = (
        "You are an elite AI engineer specializing in cement plant Pyroprocessing optimization. "
        "Analyze the inputs and KPIs, then use your domain knowledge to generate the single best set of prescriptive recommendations. "
        "Crucially, your recommendations for 'magnitude' MUST be small, safe adjustments that aim to keep the variable within its NORMAL OPERATING RANGE, unless a KPI is critically out of bounds. "
        
        "\n\n--- OPTIMIZATION GOALS ---"
        f"\n1. **Primary Goal (Quality):** Maintain Clinker Free Lime ($\%$clinker\_free\_lime) **at or below {FREE_LIME_TARGET_MAX}$\%$**. Blending component feed rates are the primary levers for this, as their effect is **lagged (approx. 5 hours)**."
        f"\n2. **Secondary Goal (Energy):** Minimize Specific Thermal Energy (kiln\_specific\_thermal\_energy\_Kcal/kg\_clinker) **toward or below {THERMAL_ENERGY_TARGET_MIN} Kcal/kg**. Fuel inputs and kiln conditions are the primary controls for this, as their effects are **real-time/non-lagged**."
        "\n3. **General Constraint:** Do not recommend changes to more than two or three variables simultaneously."
        
        "\n\n--- REQUIRED OUTPUT SCHEMA (STRICTLY FOLLOW THIS JSON ARRAY) ---"
        "[\n { \n \"variable\_name\": \"string (MUST be one of the input keys)\", "
        "\n \"description\": \"string (Detailed, prescriptive reason for the action based on domain knowledge, referencing the current and target state.)\","
        "\n \"action\": \"string (MUST be INCREASE, DECREASE, or MAINTAIN)\","
        "\n \"magnitude\": \"number (The specific value to change. Must be 0.0 if action is MAINTAIN.)\" \n }\n]"
    )
    
    # 2. Prepare the user prompt with the current data and full context
    context_lines = [f"- **{var}**: {range_str}" for var, range_str in CONTROLLABLE_RANGES.items()]
    
    user_prompt = (
        "Based on the following data, generate the prescriptive recommendations JSON array: "
        "\n\n--- PREDICTED KPI VALUES ---"
        f"\n{json.dumps(predicted_kpis, indent=2)}"
        "\n\n--- CURRENT PROCESS INPUTS (All 11 Independent Variables) ---"
        f"\n{json.dumps(current_inputs, indent=2)}"
        "\n\n--- NORMAL OPERATING RANGES FOR CONTROLLABLE VARIABLES ---"
        f"\n{chr(10).join(context_lines)}" 
        "\n\nNow, generate the JSON output, prioritizing the maintenance of quality and using small, safe magnitudes that respect the Normal Operating Ranges."
    )
    
    # 3. Call the Gemini API
    gemini_client = get_gemini_client()

    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[user_prompt],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.1 # Keep low for deterministic, reliable output
        )
    )

    # 4. Parse and return the JSON response
    return json.loads(response.text)

# -----------------------------------------------------------------------------

# --- 4. MAIN ENTRY POINT HANDLER ---

@app.route('/', methods=['POST', 'OPTIONS'])
def flask_route_recommendations(request_param=None):
    """Main route for prescriptive recommendations."""
    
    # Handle CORS preflight request
    if flask_request.method == 'OPTIONS':
        response = app.response_class(response='', status=204, mimetype='text/plain')
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        request_json = flask_request.get_json(silent=True) 

        if not request_json:
            raise ValueError("Invalid JSON or empty request body. Expected 'current_inputs' and 'predicted_kpis'.")

        current_inputs = request_json.get('current_inputs', {})
        predicted_kpis = request_json.get('predicted_kpis', {})

        if not current_inputs or not predicted_kpis:
             raise KeyError("Missing 'current_inputs' or 'predicted_kpis' in the JSON payload.")

        # Call the core LLM logic function
        recommendations = generate_recommendations_llm(current_inputs, predicted_kpis)
        
        flask_response = jsonify(recommendations)
        flask_response.status_code = 200
        flask_response.headers.add('Access-Control-Allow-Origin', '*')
        return flask_response

    except Exception as e:
        print(f"Error processing request: {e}")
        error_response = jsonify({"error": str(e), "message": "The LLM recommendation engine encountered an error. Please check the logs."})
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({"status": "healthy", "service": "llm-prescriptive-recommendations"}), 200

# --- 5. STANDALONE SERVER STARTUP ---

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)