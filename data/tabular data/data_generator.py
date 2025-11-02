import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
NUM_POINTS = 50000
INTERVAL_MINUTES = 15

# --- 2. DEFINE NORMAL OPERATING RANGES ---
limestone_feed_rate_mean = 78.0
clay_feed_rate_mean = 16.0
iron_ore_feed_rate_mean = 3.5
bauxite_feed_rate_mean = 2.5
raw_meal_feed_rate_mean = 175.0
raw_meal_feed_rate_std = 5.0
fuel_feed_rate_mean = 9.5
fuel_feed_rate_std = 0.3
fuel_alt_substitution_rate_mean = 15.0
fuel_alt_substitution_rate_std = 2.0
kiln_hood_pressure_mean = -6.0
kiln_hood_pressure_std = 0.5
kiln_burner_air_flow_mean = 25000
kiln_burner_air_flow_std = 500
clinker_feed_rate_mill_mean = 110.0
clinker_feed_rate_mill_std = 3.0
gypsum_feed_rate_mean = 5.5
gypsum_feed_rate_std = 0.2
mill_recirculation_ratio_mean = 55.0
mill_recirculation_ratio_std = 5.0
kiln_main_drive_current_mean = 200.0
kiln_main_drive_current_std = 5.0

# --- 3. GENERATE BASE DATA ---
np.random.seed(42)
timestamps = [datetime.now() - timedelta(minutes=i*INTERVAL_MINUTES) for i in range(NUM_POINTS)]
data = pd.DataFrame({'timestamp': timestamps})

# Generate Raw Material Feeds
data['limestone_feed_rate_%'] = np.random.normal(limestone_feed_rate_mean, 1.5, NUM_POINTS)
data['clay_feed_rate_%'] = np.random.normal(clay_feed_rate_mean, 1.0, NUM_POINTS)
data['iron_ore_feed_rate_%'] = np.random.normal(iron_ore_feed_rate_mean, 0.3, NUM_POINTS)
data['bauxite_feed_rate_%'] = 100 - (data['limestone_feed_rate_%'] + data['clay_feed_rate_%'] + data['iron_ore_feed_rate_%'])
data['raw_meal_feed_rate_tph'] = np.random.normal(raw_meal_feed_rate_mean, raw_meal_feed_rate_std, NUM_POINTS)
data['fuel_feed_rate_tph'] = np.random.normal(fuel_feed_rate_mean, fuel_feed_rate_std, NUM_POINTS)
data['fuel_alt_substitution_rate_%'] = np.random.normal(fuel_alt_substitution_rate_mean, fuel_alt_substitution_rate_std, NUM_POINTS)
data['kiln_hood_pressure_mmH2O'] = np.random.normal(kiln_hood_pressure_mean, kiln_hood_pressure_std, NUM_POINTS)
data['kiln_burner_air_flow_m3/hr'] = np.random.normal(kiln_burner_air_flow_mean, kiln_burner_air_flow_std, NUM_POINTS)
data['clinker_feed_rate_tph'] = np.random.normal(clinker_feed_rate_mill_mean, clinker_feed_rate_mill_std, NUM_POINTS)
data['gypsum_feed_rate_tph'] = np.random.normal(gypsum_feed_rate_mean, gypsum_feed_rate_std, NUM_POINTS)
data['mill_recirculation_ratio_%'] = np.random.normal(mill_recirculation_ratio_mean, mill_recirculation_ratio_std, NUM_POINTS)
data['kiln_main_drive_current_Amp'] = np.random.normal(kiln_main_drive_current_mean, kiln_main_drive_current_std, NUM_POINTS)


# --- 4. SIMULATE TARGET KPIs BASED ON INSTANTANEOUS INPUTS ---
data['raw_meal_lsf_ratio'] = 95 + (data['limestone_feed_rate_%'] - limestone_feed_rate_mean) * 2.5 + np.random.normal(0, 0.5, NUM_POINTS)
data['clinker_free_lime_%'] = 1.0 - (data['fuel_feed_rate_tph'] - fuel_feed_rate_mean) * 0.5 + (data['raw_meal_lsf_ratio'] - 95) * 0.4 + np.random.normal(0, 0.1, NUM_POINTS)
data['kiln_specific_thermal_energy_Kcal/kg_clinker'] = 750 + (data['raw_meal_feed_rate_tph'] - raw_meal_feed_rate_mean) * 5 - (data['fuel_alt_substitution_rate_%'] - fuel_alt_substitution_rate_mean) * 2 + np.random.normal(0, 10, NUM_POINTS)
data['kiln_exit_nox_emissions_mg/Nm3'] = 400 + (data['fuel_feed_rate_tph'] - fuel_feed_rate_mean) * 50 + (data['fuel_alt_substitution_rate_%'] - fuel_alt_substitution_rate_mean) * 3 + np.random.normal(0, 20, NUM_POINTS)
data['mill_motor_power_draw_kW'] = 4800 + (data['clinker_feed_rate_tph'] - clinker_feed_rate_mill_mean) * 20 + (data['mill_recirculation_ratio_%'] - mill_recirculation_ratio_mean) * 10 - (data['clinker_free_lime_%'] - 1.0) * 50 + np.random.normal(0, 50, NUM_POINTS)
data['cement_fineness_blaine_cm2/g'] = 3600 - (data['clinker_feed_rate_tph'] - clinker_feed_rate_mill_mean) * 15 - (data['mill_motor_power_draw_kW'] - 4800) * 0.1 + np.random.normal(0, 50, NUM_POINTS)
data['mill_specific_electrical_energy_kWh/ton_cement'] = data['mill_motor_power_draw_kW'] / (data['clinker_feed_rate_tph'] + data['gypsum_feed_rate_tph'])

# --- 5. INTRODUCE PROBLEMATIC SCENARIOS (ANOMALIES) ---
num_problems = int(len(data) * 0.15)
num_scenarios = 3

# Scenario 1: High LSF causing poor kiln performance
high_lsf_indices = np.random.choice(data.index, num_problems // num_scenarios, replace=False)
data.loc[high_lsf_indices, 'limestone_feed_rate_%'] += np.random.uniform(4, 8, len(high_lsf_indices))
data.loc[high_lsf_indices, 'raw_meal_lsf_ratio'] = 95 + (data.loc[high_lsf_indices, 'limestone_feed_rate_%'] - limestone_feed_rate_mean) * 2.5 + np.random.normal(0, 0.5, len(high_lsf_indices))
data.loc[high_lsf_indices, 'clinker_free_lime_%'] = 1.0 + (data.loc[high_lsf_indices, 'raw_meal_lsf_ratio'] - 95) * 0.4 + np.random.uniform(1.0, 1.5, len(high_lsf_indices))

# Scenario 2: Mill inefficiency
mill_ineff_indices = np.random.choice(data.index, num_problems // num_scenarios, replace=False)
data.loc[mill_ineff_indices, 'mill_motor_power_draw_kW'] += np.random.uniform(200, 400, len(mill_ineff_indices))
data.loc[mill_ineff_indices, 'cement_fineness_blaine_cm2/g'] -= np.random.uniform(300, 500, len(mill_ineff_indices))
data.loc[mill_ineff_indices, 'mill_specific_electrical_energy_kWh/ton_cement'] = data.loc[mill_ineff_indices, 'mill_motor_power_draw_kW'] / (data.loc[mill_ineff_indices, 'clinker_feed_rate_tph'] + data.loc[mill_ineff_indices, 'gypsum_feed_rate_tph'])

# Scenario 3: Kiln instability with main drive current spikes
kiln_instability_indices = np.random.choice(data.index, num_problems // num_scenarios, replace=False)
data.loc[kiln_instability_indices, 'kiln_main_drive_current_Amp'] += np.random.uniform(30, 60, len(kiln_instability_indices))
data.loc[kiln_instability_indices, 'clinker_free_lime_%'] += np.random.uniform(0.5, 0.8, len(kiln_instability_indices))
data.loc[kiln_instability_indices, 'kiln_specific_thermal_energy_Kcal/kg_clinker'] += np.random.uniform(50, 80, len(kiln_instability_indices))

# --- 6. FINALIZE AND SAVE DATA ---
data = data.round(2)

# Set the final column order with the original names
column_order = [
    'timestamp', 'limestone_feed_rate_%', 'clay_feed_rate_%', 'iron_ore_feed_rate_%', 'bauxite_feed_rate_%',
    'raw_meal_feed_rate_tph', 'fuel_feed_rate_tph', 'fuel_alt_substitution_rate_%',
    'kiln_hood_pressure_mmH2O', 'kiln_burner_air_flow_m3/hr', 'kiln_main_drive_current_Amp',
    'clinker_feed_rate_tph', 'gypsum_feed_rate_tph', 'mill_recirculation_ratio_%', 'raw_meal_lsf_ratio', 'clinker_free_lime_%',
    'kiln_specific_thermal_energy_Kcal/kg_clinker', 'kiln_exit_nox_emissions_mg/Nm3', 'mill_motor_power_draw_kW',
    'mill_specific_electrical_energy_kWh/ton_cement', 'cement_fineness_blaine_cm2/g'
]
data = data[column_order]

# *** Sanitize column names for BigQuery compatibility ***
bq_friendly_columns = [
    'timestamp', 'limestone_feed_rate_pct', 'clay_feed_rate_pct', 'iron_ore_feed_rate_pct', 'bauxite_feed_rate_pct',
    'raw_meal_feed_rate_tph', 'fuel_feed_rate_tph', 'fuel_alt_substitution_rate_pct',
    'kiln_hood_pressure_mmH2O', 'kiln_burner_air_flow_m3_hr', 'kiln_main_drive_current_amp',
    'clinker_feed_rate_tph', 'gypsum_feed_rate_tph', 'mill_recirculation_ratio_pct', 'raw_meal_lsf_ratio', 'clinker_free_lime_pct',
    'kiln_specific_thermal_energy_kcal_per_kg_clinker', 'kiln_exit_nox_emissions_mg_per_nm3',
    'mill_motor_power_draw_kW', 'mill_specific_electrical_energy_kwh_per_ton_cement', 'cement_fineness_blaine_cm2_per_g'
]
data.columns = bq_friendly_columns

file_path = 'synthetic_cement_plant_data_v4.csv'
data.to_csv(file_path, index=False)

print(f"Successfully generated {len(data)} raw data points with BigQuery-friendly column names.")
print(f"File saved to '{file_path}'")
print("\nFirst 5 rows of the generated data:")
print(data.head())

