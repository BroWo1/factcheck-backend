FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Expose ports
EXPOSE 8000

# Start services using a shell script
COPY ./docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Run the entrypoint script
CMD ["/app/docker-entrypoint.sh"]
