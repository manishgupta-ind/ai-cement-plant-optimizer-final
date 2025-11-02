import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import aiplatform

# --- 1. CONFIGURATION ---
# Use environment variables for Project ID and Location (Standard for Cloud Run/Functions)
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT')
LOCATION = os.environ.get('REGION', "us-central1") # Default to us-central1

# A dictionary mapping KPI names to their respective Vertex AI Endpoint IDs
# NOTE: Replace 'your-...' placeholders with actual deployed model IDs before deployment.
MODEL_ENDPOINT_IDS = {
    "clinker_free_lime_%": "6552534048172933120", # Assumed to be a live ID based on previous code
    "raw_meal_lsf_ratio": "your-raw-meal-lsf-deployed-model-id",
    "kiln_specific_thermal_energy_Kcal/kg_clinker": "your-kiln-thermal-energy-deployed-model-id",
    "kiln_exit_nox_emissions_mg/Nm3": "your-kiln-nox-deployed-model-id",
    "mill_motor_power_draw_kW": "your-mill-motor-power-deployed-model-id",
    "mill_specific_electrical_energy_kWh/ton_cement": "your-mill-specific-electrical-energy-deployed-model-id",
    "cement_fineness_blaine_cm2/g": "your-cement-fineness-deployed-model-id"
}

# Define the features required for each model
MODEL_FEATURES = {
    "clinker_free_lime_%": [
        "raw_meal_lsf_ratio", "limestone_feed_rate_pct", "clay_feed_rate_pct", 
        "iron_ore_feed_rate_pct", "bauxite_feed_rate_pct", "raw_meal_feed_rate_tph", 
        "fuel_feed_rate_tph", "fuel_alt_substitution_rate_pct", 
        "kiln_hood_pressure_mmH2O", "kiln_burner_air_flow_m3_hr",
        "kiln_main_drive_current_amp"
    ],
    "raw_meal_lsf_ratio": [
        "limestone_feed_rate_pct", "clay_feed_rate_pct", "iron_ore_feed_rate_pct", 
        "bauxite_feed_rate_pct", "raw_meal_feed_rate_tph"
    ],
    "kiln_specific_thermal_energy_Kcal/kg_clinker": [
        "raw_meal_feed_rate_tph", "fuel_feed_rate_tph", "fuel_alt_substitution_rate_pct", 
        "kiln_hood_pressure_mmH2O", "kiln_burner_air_flow_m3_hr", "kiln_main_drive_current_amp" # CORRECTED: Removed 'clinker_feed_rate_tph'
    ],
    "kiln_exit_nox_emissions_mg/Nm3": [
        "fuel_feed_rate_tph", "fuel_alt_substitution_rate_pct", "kiln_burner_air_flow_m3_hr"
    ],
    "mill_motor_power_draw_kW": [
        "clinker_feed_rate_tph", "gypsum_feed_rate_tph", "mill_recirculation_ratio_%"
    ],
    "mill_specific_electrical_energy_kWh/ton_cement": [
        "clinker_feed_rate_tph", "gypsum_feed_rate_tph", "mill_recirculation_ratio_%",
        "mill_motor_power_draw_kW"
    ],
    "cement_fineness_blaine_cm2/g": [
        "mill_recirculation_ratio_%", "mill_motor_power_draw_kW", 
        "clinker_feed_rate_tph", "gypsum_feed_rate_tph"
    ]
}

# --- 2. GLOBAL INITIALIZATION ---
# Initialize the Vertex AI client once at the global scope
if PROJECT_ID:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
else:
    print("WARNING: GOOGLE_CLOUD_PROJECT not set. Vertex AI client will not be initialized.")

# Initialize all required Vertex AI Endpoint objects once at the global scope
global_endpoints = {}
for kpi, endpoint_id in MODEL_ENDPOINT_IDS.items():
    if PROJECT_ID and endpoint_id and not endpoint_id.startswith("your-"):
        try:
            global_endpoints[kpi] = aiplatform.Endpoint(endpoint_name=endpoint_id)
            print(f"Successfully initialized endpoint for {kpi}")
        except Exception as e:
            print(f"Failed to initialize endpoint for {kpi}: {e}")

# Initialize the Flask application
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

def get_vertex_prediction(endpoint: aiplatform.Endpoint, input_data: dict) -> float:
    """
    Sends input data to a specified Vertex AI deployed model and returns the prediction.
    """
    try:
        # Format the data for the API request: a list containing one instance dictionary
        instance = [{key: value for key, value in input_data.items()}]
        
        response = endpoint.predict(instances=instance)
        
        # Check for the expected response format (for regression models)
        if response and response.predictions and response.predictions[0] is not None:
            prediction = response.predictions[0]
            
            # Handle common Vertex AI prediction outputs (either {'value': X} or just X)
            if isinstance(prediction, dict) and 'value' in prediction:
                return float(prediction['value'])
            elif isinstance(prediction, (int, float)):
                return float(prediction)
        
        print(f"Vertex AI prediction response was not in the expected format. Response: {response}")
        return None

    except Exception as e:
        print(f"An error occurred during prediction: {e}")
        return None

# --- 3. MAIN ENTRY POINT HANDLER ---

@app.route('/', methods=['POST', 'OPTIONS'])
def flask_route():
    """Flask route that calls the main prediction logic."""
    return flask_predict()

def flask_predict(request_param=None):
    """
    Main prediction logic to run predictions for the target KPI (clinker_free_lime_%).
    The primary goal of this specific service appears to be the Free Lime prediction.
    """
    from flask import request as flask_request
    current_request = request_param if request_param is not None else flask_request
    
    # Handle CORS preflight request
    if current_request.method == 'OPTIONS':
        response = jsonify({'status': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response, 200
    
    try:
        request_json = current_request.get_json(silent=False)
        if request_json is None:
            raise ValueError("The request body is empty or not a valid JSON.")
        
        # This service is designed to return the prediction for clinker_free_lime_%
        kpi_to_predict = "clinker_free_lime_%"
        
        # 1. Initialize prediction result
        predictions = {kpi_to_predict: None}
        
        # 2. Get the pre-initialized endpoint object
        endpoint = global_endpoints.get(kpi_to_predict)
        
        if not endpoint:
            print(f"WARNING: Endpoint for '{kpi_to_predict}' not initialized. Check endpoint ID.")
        else:
            required_features = MODEL_FEATURES.get(kpi_to_predict, [])
            input_data = {
                feature: request_json.get(feature) for feature in required_features
            }

            # 3. Check for missing features
            missing_features = [f for f, v in input_data.items() if v is None]
            if missing_features:
                print(f"WARNING: Missing data for features: {missing_features}")
                predictions[kpi_to_predict] = None # Set to None for API error handling
            else:
                # Convert values to float for consistency
                input_data_float = {k: float(v) for k, v in input_data.items()}
                
                # 4. Get prediction from Vertex AI
                predicted_value = get_vertex_prediction(endpoint, input_data_float)
                
                if predicted_value is not None:
                    # Format the prediction to 2 decimal places
                    predictions[kpi_to_predict] = round(predicted_value, 2)
                else:
                    predictions[kpi_to_predict] = None

        final_response_data = {
            "clinker_free_lime_%": predictions["clinker_free_lime_%"]
        }
        
        response = jsonify(final_response_data)
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200

    except ValueError as ve:
        error_response = jsonify({"error": str(ve)})
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 400
    except Exception as e:
        print(f"Error processing request: {e}")
        error_response = jsonify({"error": "An internal server error occurred."})
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)