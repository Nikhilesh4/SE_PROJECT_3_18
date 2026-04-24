# Task 1: Requirements and Subsystems
## 1. Functional Requirements (FR)
Functional requirements define the core capabilities and services the UniCompass system provides to its users.

- **FR-1: Multi-Source Opportunity Aggregation**
  The system shall fetch opportunities (internships, hackathons, research openings, courses) from various sources including RSS feeds (e.g., Internshala, HackerEarth) and external Job APIs (Adzuna, Jooble, Semantic Scholar).
  
- **FR-2: AI-Powered Profile Extraction**
  The system shall allow users to upload PDF resumes and automatically extract structured data such as skills, education, and experience using the Gemini API to populate user profiles.

- **FR-3: Unified Discovery Feed**
  The system shall present a consolidated feed of opportunities that can be filtered by category and sorted by "Latest" or "Most Relevant".

- **FR-4: Semantic Matching & Personalized Ranking**
  The system shall use vector embeddings (Sentence-Transformers) and similarity search (pgvector) to rank opportunities according to the user's extracted skills and interests.

- **FR-5: Real-Time Notifications**
  The system shall notify users in real-time via WebSockets when new opportunities that strongly match their profile are ingested into the database.

- **FR-6: Opportunity Bookmarking**
  Users shall be able to save/bookmark specific opportunities for future reference and easy access.

- **FR-7: Authentication & User Management**
  The system shall provide secure user registration and login functionality using JWT-based authentication.

## 2. Non-Functional Requirements (NFR)
Non-functional requirements specify the quality attributes, performance targets, and constraints of the system.

- **NFR-1: Performance (Low Latency)**
  The discovery feed should load in under 200ms for cached requests. This is achieved through a multi-layer Redis caching strategy for feeds and individual opportunities.

- **NFR-2: Scalability**
  The background ingestion engine must be able to handle hundreds of concurrent RSS feeds and API sources without impacting the responsiveness or stability of the main web API.

- **NFR-3: Accuracy (Relevance)**
  The semantic matching engine should provide high-relevance rankings, ensuring users see the most appropriate opportunities based on their professional background.

- **NFR-4: Availability**
  The system should ensure that background workers are resilient to network failures and that real-time notification services remain connected during active user sessions.

- **NFR-5: Data Deduplication**
  The system must ensure that duplicate opportunities from different sources are identified (via source URLs) and merged into a single entry to prevent clutter in the feed.

## 3. Architecturally Significant Requirements
These are the key requirements that have a major impact on the system’s design and architectural choices:

- **Background Data Ingestion**: The requirement to aggregate high-volume data from fragmented external sources necessitated a decoupled ingestion architecture. Background workers avoid blocking the main API thread during long-running network operations.
- **Semantic Personalization**: The need for "Relevance-based" sorting required the integration of a vector database extension (`pgvector`) and an embedding pipeline, which is a significant architectural shift from traditional keyword-based filtering.
- **Real-Time Event Driven Updates**: The real-time notification requirement led to the implementation of the **Observer/Pub-Sub** pattern (via Redis) and WebSockets, allowing the backend to push data to the frontend proactively.
- **Unified Data Normalization**: The variety of source formats (RSS, JSON APIs) dictated the use of the **Facade & Adapter** design patterns to normalize data into a standard `OpportunityCard` format at the architectural level.

## 4. Subsystem Overview

The UniCompass system is divided into several logical subsystems, each with a specific role:

| Subsystem | Description | Key Technologies |
| :--- | :--- | :--- |
| **Frontend UI** | Manages user interaction, displays the discovery feed, provides profile management interfaces, and renders real-time notifications. | React, Next.js, TailwindCSS |
| **Backend API** | Orchestrates business logic, manages user authentication, provides RESTful endpoints, and handles application state. | Python, FastAPI, JWT |
| **Ingestion Engine** | A dedicated background process that polls RSS feeds and external APIs, parses content, and normalizes it for storage. | Feedparser, External APIs |
| **Matching Engine** | Generates embeddings for opportunities and profiles; performs vector similarity searches to enable personalized rankings. | Sentence-Transformers, pgvector |
| **Persistence Layer** | Handles structured data storage (users/opportunities) and high-speed caching/message brokering for inter-service communication. | PostgreSQL, Redis |
| **AI/ML Service** | Provides intelligent processing for unstructured data, specifically extracting structured profile information from PDF resumes. | Gemini API, PyMuPDF |
