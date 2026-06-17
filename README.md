# EVE: Agentic Multi-Agent Orchestrator

EVE is a decoupled, asynchronous, and scalable AI system that transforms raw data into actionable knowledge. Unlike standard chatbot interfaces, EVE acts as a persistent backend controller for personal infrastructure.

## Architecture
EVE operates on a modular "Hive Mind" pattern:
*   **Queen Bee (Orchestrator)**: Manages request routing and lifecycle.
*   **Worker Bees (Concurrent Agents)**: Utilize Llama 3.3 to process segments of a task in parallel.
*   **Main Agent (Judge)**: Synthesizes worker outputs and verifies consensus against ground truth (Supabase).
*   **SecondBrain RAG**: A persistent vector database ensuring all AI actions are grounded in the user's personal context and documentation.

## Core Features
*   **Agentic RAG**: Persistent knowledge retrieval that evolves through hierarchical summarization.
*   **Multi-Agent Consensus**: Parallel agent processing for high-accuracy decision making.
*   **Action Engine**: Capability to trigger external browser/system events via structured JSON communication (e.g., automated link opening).
*   **Automated Lifecycle**: Future-integrated file cleaning and organization agents to maintain Drive hygiene.

## Tech Stack
*   **Backend**: FastAPI (Python)
*   **Orchestration**: Asyncio, Custom Multi-Agent Pattern
*   **Database**: Supabase (PostgreSQL/Vector Storage)
*   **External APIs**: Google Drive API, Groq (Llama 3.3), Gemini Flash
*   **Deployment**: Render (Cloud Infrastructure)

## Quick Start
1. Clone the repository.
2. Set up environment variables for Supabase, Google Drive, and API providers.
3. Deploy via Render using the provided `render.yaml`.
4. Initialize the Queen Bee orchestrator to begin agentic processing.

---
*Built as a modular framework for automated personal knowledge systems.*
