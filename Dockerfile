# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose the port for Cloud Run (default is 8080)
EXPOSE 8080

# Cloud Run sets the PORT environment variable.
# Run Streamlit on that port.
CMD streamlit run dashboard/app.py --server.port="${PORT:-8080}" --server.address="0.0.0.0"
