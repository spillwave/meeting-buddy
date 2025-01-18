FROM ollama/ollama:latest

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Expose the default Ollama port
EXPOSE 11434

# Set environment variable to enable GPU
ENV OLLAMA_HOST=0.0.0.0

# Start Ollama service and the application
CMD ["sh", "-c", "ollama serve & python3 app.py"]
