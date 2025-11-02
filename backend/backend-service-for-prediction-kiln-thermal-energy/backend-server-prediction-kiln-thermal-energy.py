import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import aiplatform

# --- 1. CONFIGURATION ---
# Use environment variables for Project ID and Location, which is standard for Cloud Run.
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT')
LOCATION = os.environ.get('REGION', "us-central1") # Default to us-central1

# A dictionary mapping KPI names to their respective Vertex AI Endpoint IDs
MODEL_ENDPOINT_IDS = {
    # The ID for the Thermal Energy Model
    "kiln_specific_thermal_energy_Kcal/kg_clinker": "8596851619650338816",
    # Placeholder for the Free Lime model, kept for structure reference
    "clinker_free_lime_%": "6552534048172933120", 
}

# Define the features required for the Thermal Energy model (as confirmed by Model Documentation.docx)
MODEL_FEATURES = {
    "kiln_specific_thermal_energy_Kcal/kg_clinker": [
        "raw_meal_feed_rate_tph", 
        "fuel_feed_rate_tph", 
        "fuel_alt_substitution_rate_pct", 
        "kiln_hood_pressure_mmH2O", 
        "kiln_burner_air_flow_m3_hr", 
        "kiln_main_drive_current_amp"
    ],
    # Other features are not relevant to this specific service, but structure remains clean
}

# --- 2. GLOBAL INITIALIZATION ---
# Initialize the Vertex AI client once
if PROJECT_ID:
    aiplatform.init(project=PROJECT_ID, location=LOCATION)
    print(f"Vertex AI Client initialized for Project: {PROJECT_ID}")
else:
    print("WARNING: GOOGLE_CLOUD_PROJECT environment variable not set. Vertex AI client not initialized.")


global_endpoints = {}
TARGET_KPI = "kiln_specific_thermal_energy_Kcal/kg_clinker"

try:
    endpoint_id = MODEL_ENDPOINT_IDS[TARGET_KPI]
    if PROJECT_ID and endpoint_id and not endpoint_id.startswith("your-"):
        # Initialize the Endpoint object
        global_endpoints[TARGET_KPI] = aiplatform.Endpoint(endpoint_name=endpoint_id)
        print(f"Successfully initialized endpoint for {TARGET_KPI} (ID: {endpoint_id})")
    else:
        print(f"WARNING: Skipping initialization for {TARGET_KPI}. Endpoint ID or Project ID is missing.")
except Exception as e:
    print(f"Failed to initialize endpoint for {TARGET_KPI}: {e}")

# Initialize the Flask application and CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

def get_vertex_prediction(endpoint: aiplatform.Endpoint, input_data: dict) -> float:
    """
    Sends input data to a specified Vertex AI deployed model and returns the prediction.
    """
    try:
        # Format the data for the API request: a list containing one instance dictionary
        instance = [{key: value for key, value in input_data.items()}]
        
        # Call the prediction service
        response = endpoint.predict(instances=instance)
        
        # Extract the prediction value (assuming the response format for regression)
        if response and response.predictions and response.predictions[0] is not None:
            prediction = response.predictions[0]
            if isinstance(prediction, dict) and 'value' in prediction:
                return prediction['value']
            elif isinstance(prediction, (int, float)):
                return float(prediction)
        
        print(f"Vertex AI prediction response was not in the expected format. Response: {response}")
        return None

    except Exception as e:
        print(f"An error occurred during prediction: {e}")
        return None

@app.route('/', methods=['POST', 'OPTIONS'])
def flask_predict(request_param=None):
    """
    Handles POST requests for prediction and CORS preflight (OPTIONS).
    This function is explicitly set up to predict the Thermal Energy KPI.
    """
    current_request = request_param if request_param is not None else request
    
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
        
        kpi_to_predict = TARGET_KPI 
        
        endpoint = global_endpoints.get(kpi_to_predict)
        
        if not endpoint:
            # If the endpoint is not ready, return a 503 Service Unavailable error
            print(f"ERROR: The endpoint for '{kpi_to_predict}' is not configured or initialized.")
            error_response = jsonify({"error": f"Prediction service is unavailable for {kpi_to_predict}."})
            error_response.headers.add('Access-Control-Allow-Origin', '*')
            return error_response, 503
        
        required_features = MODEL_FEATURES.get(kpi_to_predict, [])
        # Extract only the features required by the specific model
        input_data = {
            feature: request_json.get(feature) for feature in required_features
        }

        # Check for missing features
        missing_features = [f for f, v in input_data.items() if v is None]
        if missing_features:
            error_msg = f"Missing data for required features: {missing_features}. Required: {required_features}"
            print(f"WARNING: {error_msg}")
            error_response = jsonify({"error": error_msg})
            error_response.headers.add('Access-Control-Allow-Origin', '*')
            return error_response, 400
        
        # Convert values to float for consistency, ensuring no type errors in the model call
        input_data_float = {k: float(v) for k, v in input_data.items()}
        
        # Get prediction from Vertex AI
        predicted_value = get_vertex_prediction(endpoint, input_data_float)
        
        if predicted_value is not None:
            # Format the prediction to 2 decimal places
            formatted_prediction = round(predicted_value, 2)
            
            # The response now contains only the prediction for the targeted KPI
            response_data = {
                "kiln_specific_thermal_energy_Kcal/kg_clinker": formatted_prediction
            }
            
            response = jsonify(response_data)
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            print("Prediction failed to return a valid value.")
            error_response = jsonify({"error": "Prediction returned an invalid or null value."})
            error_response.headers.add('Access-Control-Allow-Origin', '*')
            return error_response, 500

    except ValueError as ve:
        print(f"Validation error: {ve}")
        error_response = jsonify({"error": str(ve)})
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response, 400
    except Exception as e:
        print(f"Error processing request: {e}")
        error_response = jsonify({"error": f"An internal server error occurred: {e}"})
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