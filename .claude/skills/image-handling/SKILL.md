# Image Handling Skill

This skill describes how the assistant processes and understands images.

## How it Works
The image feature extends the existing chat pipeline to support multimodal inputs.

### 1. Frontend Handling
- Users upload images via the `Composer` component.
- The image is converted to a **base64 encoded string** in the browser. This allows the image to be sent as a simple string within the JSON request.

### 2. API Processing
- The `ChatMessage` schema was updated to include an `images` list.
- The backend forwards these base64 strings directly to the AI provider.

### 3. AI Vision
- The `OllamaProvider` sends the `images` array to the Ollama API.
- This requires a **Vision-capable model** (like `llava`). The model analyzes the pixel data of the image alongside the text prompt to generate a description.

### 4. Workflow
`User Upload` $\rightarrow$ `Base64 Encoding` $\rightarrow$ `FastAPI Route` $\rightarrow$ `Ollama Vision Model` $\rightarrow$ `Text Response`
