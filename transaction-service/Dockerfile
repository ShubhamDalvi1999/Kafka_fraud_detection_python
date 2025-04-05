FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

# Install Werkzeug and Flask explicitly with fixed versions first
RUN pip install --no-cache-dir werkzeug==2.0.3 flask==2.0.1

# Then install the rest of the dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3000

CMD ["python", "app.py"] 