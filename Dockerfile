# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt .

# Create and activate a virtual environment
RUN python -m venv /env && \
    /env/bin/pip install --upgrade pip && \
    /env/bin/pip install -r requirements.txt

# Set environment variables to use the virtual environment
ENV PATH="/env/bin:$PATH"

# Copy the application code to the container
COPY app/ ./app

# Expose the port Flask will run on
EXPOSE 8080

# Run the application
CMD ["python", "app/main.py"]
