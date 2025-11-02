WITH TimeShiftedData AS (
  SELECT
    timestamp,
    -- Mill KPIs (Targets) - No lag needed for the final outputs
    mill_motor_power_draw_kW,
    mill_specific_electrical_energy_kwh_per_ton_cement,
    cement_fineness_blaine_cm2_per_g,

    -- Kiln KPIs (Targets, but also inputs for Mill) - Lagged by 1 hour (4 * 15 min periods)
    LAG(clinker_free_lime_pct, 4) OVER (ORDER BY timestamp) AS clinker_free_lime_pct,
    LAG(kiln_specific_thermal_energy_kcal_per_kg_clinker, 4) OVER (ORDER BY timestamp) AS kiln_specific_thermal_energy_kcal_per_kg_clinker,
    LAG(kiln_exit_nox_emissions_mg_per_nm3, 4) OVER (ORDER BY timestamp) AS kiln_exit_nox_emissions_mg_per_nm3,

    -- Grinding Inputs - Lagged by 1 hour
    LAG(clinker_feed_rate_tph, 4) OVER (ORDER BY timestamp) AS clinker_feed_rate_tph,
    LAG(gypsum_feed_rate_tph, 4) OVER (ORDER BY timestamp) AS gypsum_feed_rate_tph,
    LAG(mill_recirculation_ratio_pct, 4) OVER (ORDER BY timestamp) AS mill_recirculation_ratio_pct,

    -- Blending and Pyro Inputs (Lagged by a total of 5 hours = 4hr + 1hr = 20 * 15 min periods)
    LAG(raw_meal_lsf_ratio, 20) OVER (ORDER BY timestamp) AS raw_meal_lsf_ratio,
    LAG(limestone_feed_rate_pct, 20) OVER (ORDER BY timestamp) AS limestone_feed_rate_pct,
    LAG(clay_feed_rate_pct, 20) OVER (ORDER BY timestamp) AS clay_feed_rate_pct,
    LAG(iron_ore_feed_rate_pct, 20) OVER (ORDER BY timestamp) AS iron_ore_feed_rate_pct,
    LAG(bauxite_feed_rate_pct, 20) OVER (ORDER BY timestamp) AS bauxite_feed_rate_pct,
    LAG(raw_meal_feed_rate_tph, 20) OVER (ORDER BY timestamp) AS raw_meal_feed_rate_tph,
    LAG(fuel_feed_rate_tph, 20) OVER (ORDER BY timestamp) AS fuel_feed_rate_tph,
    LAG(fuel_alt_substitution_rate_pct, 20) OVER (ORDER BY timestamp) AS fuel_alt_substitution_rate_pct,
    LAG(kiln_hood_pressure_mmH2O, 20) OVER (ORDER BY timestamp) AS kiln_hood_pressure_mmH2O,
    LAG(kiln_burner_air_flow_m3_hr, 20) OVER (ORDER BY timestamp) AS kiln_burner_air_flow_m3_hr,
    LAG(kiln_main_drive_current_amp, 20) OVER (ORDER BY timestamp) AS kiln_main_drive_current_amp -- NEWLY ADDED

  FROM
    -- Make sure this table name matches the one you created from the latest CSV file
    `<PROJECT-ID>.cement_plant_data.raw_plant_readings`
)
SELECT * FROM TimeShiftedData WHERE raw_meal_lsf_ratio IS NOT NULL