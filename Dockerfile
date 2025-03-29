FROM ubuntu:noble

# Update and install system dependencies
RUN apt-get update && \
    apt-get install -y python3-pip python3-dev 

# Copy the requirements file
COPY requirements.txt /tmp

# Install python packages
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt --break-system-packages

RUN mkdir /input /output /app
# Set working directory
WORKDIR /app

# Copy the Python application code
COPY *.py .

# Set the entrypoint command
ENTRYPOINT ["python3", "/app/hass_backup_decrypt.py"]
