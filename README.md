# ⚙️ Project CINDER: The Autonomous Generative AI Co-Pilot for Cement Kilns

## 🌟 Introduction & Problem Solved

**Project CINDER** is a real-time, prescriptive control system built on Google Cloud AI, designed to manage the two most critical and conflicting variables in cement manufacturing: **Clinker Quality (Free Lime)** and **Thermal Energy Cost**.

The industry's core challenge is the **5-hour process lag** between raw material blending and final quality results, which forces operators into costly, reactive control actions.

| Component | Detail |
| :--- | :--- |
| **Product Focus** | Provides end-to-end, real-time **Generative AI recommendations** for Kiln control. |
| **Target User** | Kiln Control Room Operators and Process Engineers. |
| **Main Outcome** | Guarantees product quality while safely **maximizing Alternative Fuel (AF) substitution** to reduce Specific Thermal Energy (STE) costs by **3-5%**. |

---

## 💡 Core Innovation: Generative AI for Prescriptive Control

Project CINDER moves beyond simple predictive modeling by integrating **Generative AI** as the core decision engine, providing a unified, low-risk solution.

1.  **Dual-Model Foresight:** We solve the 5-hour process lag by running **two concurrent predictions** on Vertex AI: a **5-hour Quality Forecast** (Clinker Free Lime %) and a **Real-Time Energy Cost Model**.
2.  **Qualitative Context Fusion:** **Google Cloud Vision** analyzes unstructured data (Kiln Flame stability images) in real-time. This qualitative feedback makes the system's decisions safer and more trustworthy than pure numerical models.
3.  **Generative Reasoning:** The **Gemini API** synthesizes all inputs (conflicting KPI predictions + visual context) to generate a single, non-breaking, natural language **prescriptive setpoint**. This replaces operator guesswork with an authoritative command (e.g., "Increase Limestone Feed Rate by +0.7%...").

---

## 🏗️ Architecture & Tech Stack

The system is built on a scalable, event-driven architecture optimized for low-latency, real-time control decisions.

### Process Flow: The Autonomous Control Loop

1.  **Ingestion:** Real-time telemetry streams from sensors/UI to the **Cloud Run** backend.
2.  **Concurrent AI Calls:** Cloud Run orchestrates calls to **Vertex AI Endpoints** (for dual prediction) and **Cloud Vision** (for image analysis).
3.  **Generative Synthesis:** The combined data is fed to the **Gemini API** for setpoint generation.
4.  **Execution:** The prescriptive setpoint is delivered to the operator UI, closing the loop.

### Tech Stack Summary

| Layer | Tools Used | Justification |
| :--- | :--- | :--- |
| **Generative AI & Reasoning** | **Gemini API** (via Vertex AI) | Generates actionable, human-readable control commands. |
| **Machine Learning Core** | **Vertex AI Endpoints** (AutoML) | Hosts two production-ready ML models for high-speed, low-latency scoring. |
| **Compute & Orchestration** | **Cloud Run**, Python/Flask | Provides a highly scalable, serverless, and cost-efficient backend. |
| **Contextual Intelligence** | **Google Cloud Vision API** | Integrates qualitative, visual context for decision-making robustness. |
| **Data Lake & Training** | **BigQuery** | Stores historical data used *exclusively* for model training and retraining. |

---

## 💰 Market Viability & Adoption Roadmap

### Financial Viability

| Element | Detail |
| :--- | :--- |
| **Monthly Cost to Run** | Estimated **\$200 - \$500 per kiln/month** (leveraging Cloud Run's scale-to-zero and pay-per-use APIs). |
| **Return on Investment (ROI)** | **3-5% reduction in Specific Thermal Energy (STE)** translates to significant monthly savings, projecting an ROI in **6-12 months** per deployed kiln. |

### Next 30-90 Day Plan

| Timeline | Focus Area | Goal |
| :--- | :--- | :--- |
| **Day 0-30** | **Data Stream & Validation** | Secure a pilot data agreement and integrate the **Cloud Run backend** with the plant historian. |
| **Day 30-60** | **Recommendation-Only Mode** | Launch the system to validate the **5-hour forecast accuracy** and measure operator adoption of the **Generative Setpoints**. |
| **Day 60-90** | **Closed-Loop Preparation** | Quantify the achieved thermal energy savings ($\triangle$STE). Prepare for the deployment of **Closed-Loop Autonomous Control** on a single, stable parameter. |

---

## 📺 Demo Video

**The full journey runs end-to-end without breaking.**

https://drive.google.com/file/d/17HERe76aduNLt8Gr4YjHhMRRxEGiRRk1/