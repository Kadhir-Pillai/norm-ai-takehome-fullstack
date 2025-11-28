# Norm AI Take-Home: GOT Legal Assistant

This repository contains the code for a legal assistant AI designed to help users with legal inquiries related to the 
laws of The Seven Kingdoms from the Game of Thrones universe. The AI leverages RAG (Retrieval-Augmented Generation)
techniques to provide accurate and contextually relevant legal information.

## Requirements

- OpenAI API Key
- Docker
- Node.js

## How to Run
### Running Backend
1. Create .env file in root directory with the following content:
   ```
   OPENAI_API_KEY=insert_openai_api_key_here
   ```
2. Build and run the Docker container for the backend:
   ```bash
   docker build -t westeros-legal-ai .
   docker run -p 80:80 --env-file ./.env westeros-legal-ai
   ```
3. Access the backend API swagger documentation at `http://localhost/docs`
4. You can try the service by clicking "Try it out" in the swagger page for the /query endpoint and filling in the
   q field with your question.

### Running Frontend
1. In a separate terminal, navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install the dependencies:
   ```bash
   npm install
   ```
3. Start the frontend development server:
   ```bash
   npm run dev
   ```
4. Navigate to `http://localhost:3000` in your web browser and start asking questions from the textbox

## Process Details
### Backend Flow
- Document Creation
  - The process reads legal documents from the /docs directory and splits them into a `Document` object for each 
  section with non-title content in the `DocumentService` class' `create_documents` method
  - The metadata for the `Document` objects consists of the section number, section title, and source document (Always 
  "Laws of the Seven Kingdoms" since only one legal document provided) as metadata
- Index Creation
  - Index is created and populated by the `QdrantService` class' `connect` and `load` methods
  - It uses OpenAI's text-embedding-3-small model to embed the documents
  - The documents are stored in a vector store index backed by an in-memory Qdrant vector store
- Querying
  - Queries are handled by the `QdrantService` class' `query` method 
  - When it receives a query, it prefixes it with additional instructions to ensure the response is 
  relevant and precise
  - It then uses the `CitationQueryEngine` to retrieve the top k relevant documents (k=2 by default) using the index 
  and send the query with context to GPT-4o to generate a response with citations
  - The query, response, and enumerated citations are returned to the user
### Frontend Flow
- The frontend is a simple React application that provides a textbox for users to input their legal questions
- When the user submits a question, it sends a request to the backend API's /query endpoint
- The response from the backend is displayed on the frontend, showing the answer along with the retrieved citations
with the legal document and section number it came from displayed
- Links are created from the in-text citation numbers to their corresponding citation details below for easy reference

## Reflective Response
The high-level of precision required for legal inquiries means that extensive measures will need to be put
in place to ensure accuracy at all locations in the flow. One such place would be when parsing the documents. An error
in parsing a specific law can be potentially disastrous as it could cause erroneous responses in an entire class of
queries relevant to said law. This is also made particularly difficult in the absence of standardization as small
abnormalities in the format of legal documents could result in disastrous consequences if the parsing logic is not
flexible enough. One way to tackle this issue is by gathering a large, representative corpus of documents and applying
rigorous tests to ensure the validity of the parsing logic. Additionally, formatting requirements could be enforced 
before inclusion in the knowledge base and a separate (possibly also AI-based) flow could be created to reformat 
documents into the desired format.

The precision requirements also mean that measures would need to be taken to ensure consistent accuracy in the 
response. This could be done by adding stages of self-critique regarding the applicability of retrieved data and 
applicability of the response and implementing rigorous validation workflows that must be passed to release/update 
workflows and prompts. These validation workflows would need to cover the full range of potential tasks with 
finely-crafted model responses and possibly a separate AI-based flow to score generated responses.

With legal AI flows, some users will likely feel uncertain about the accuracy of the responses regardless of what the
metrics indicate. To ensure user confidence there are some additional measures that can be implemented. One measure
is transparency of as much of the workflow as possible without revealing any proprietary information (e.g. relevant
documents/laws and reasoning at different stages) in the UI. Another way to increase user confidence is by ensuring 
internal consistency through maintaining some memory of past responses with RAG retrieval (preferring approved 
responses if user feedback is present) for additional context when responding.

A final potential challenge is regarding changes in the law which can happen either through new laws/amendments getting 
passed or by legal precedents being created/overturned by courts. Amendments can be handled by a separate flow which
updates legal documents as amendments are passed in different jurisdictions. In the case of new laws (like a new 
Federal law overriding a recorded State law), proper metadata could be maintained and provided in the prompt, 
offloading the determination of which law to apply to runtime. To handle legal precedent updates, there could be a
stage in the response flow to retrieve relevant text chunks after the relevant laws have been retrieved with temporal
data and source data (if it's necessary to determine which court has the greater authority) included in the prompt to 
allow the model to determine what the relevant precedent is.
