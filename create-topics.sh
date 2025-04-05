#!/bin/bash

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
sleep 10

# Create the transactions topic with 10 partitions
echo "Creating 'transactions' topic with 10 partitions..."
docker exec -it kafka-real-time-fraud-detection-kafka-1 kafka-topics.sh \
    --bootstrap-server kafka:9092 \
    --create \
    --topic transactions \
    --partitions 10 \
    --replication-factor 1 \
    --if-not-exists

# Create the fraud-alerts topic with 5 partitions
echo "Creating 'fraud-alerts' topic with 5 partitions..."
docker exec -it kafka-real-time-fraud-detection-kafka-1 kafka-topics.sh \
    --bootstrap-server kafka:9092 \
    --create \
    --topic fraud-alerts \
    --partitions 5 \
    --replication-factor 1 \
    --if-not-exists

echo "Topics created successfully!" 