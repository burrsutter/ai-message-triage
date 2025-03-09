# AI Message Triage

A Kafka-based system for automated email message analysis and triage using LLMs (Large Language Models). This project processes customer support emails through a pipeline that analyzes content, extracts key information, and routes messages based on their characteristics.

Note: This is a totally "hacked together" codebase.  Needs an investment of time to really analyze the input/output Pydantic message definitions.  Python's dynamic typing makes for some more interesting debugging opportunities when the str, dict and Pydantic models are not aligned perfectly.   A proper microservices architecture would have very strict rules over the message JSON schema making for easier testing interoperability. 

## Features

- Kafka-based message processing pipeline
- LLM-powered email analysis
- Automatic extraction of:
  - Customer information
  - Email content
  - Sentiment analysis
  - Product references
  - Escalation requirements
- Real-time message routing
- Error handling and message review system

## Architecture

The system consists of several components:
- Kafka Producer: Ingests email messages into the system
- LLM Processor: Analyzes messages using OpenAI-compatible models
- Kafka Consumer: Processes analyzed messages and routes them accordingly
- Review System: Handles edge cases and messages requiring manual review

## Prerequisites

- Python 3.x
- Apache Kafka
- OpenAI API compatible service
- Python dependencies (see requirements.txt)

## Environment Variables

Create a `.env` file with the following configurations:

```
KAFKA_INPUT_TOPIC=<input-topic-name>
KAFKA_BROKER=<kafka-broker-address>
KAFKA_OUTPUT_TOPIC=<output-topic-name>
KAFKA_REVIEW_TOPIC=<review-topic-name>
MODEL_NAME=<llm-model-name>
API_KEY=<your-api-key>
INFERENCE_SERVER_URL=<llm-server-url>
```

## Project Structure

- `kafka-in-llm-out.py`: Main application file handling message processing
- `models.py`: Pydantic models for message and email analysis
- `kafka-producer-pydantic.py`: Kafka producer implementation
- `kafka-consumer-pydantic.py`: Kafka consumer implementation
- `.env`: Environment configuration file

## Data Models

### Message
- `id`: Unique message identifier
- `content`: Raw message content
- `timestamp`: Message creation time
- `comment`: Analysis results (AnalyzedMessage)
- `error`: Error information (if any)

### AnalyzedMessage
- `reason`: Primary reason for the email
- `sentiment`: Detected sentiment
- `customer_name`: Extracted customer name
- `email_address`: Customer email address
- `product_name`: Referenced product
- `escalate`: Escalation flag

## Usage

1. install, start and configure your Kafka broker

```
brew install kafka
brew services start zookeeper
brew services start kafka
```

List of Topics:

```
/opt/homebrew/bin/kafka-topics --bootstrap-server localhost:9092 --list 
```

Delete & Create the Topics if needed:

```
chmod +x reset.sh
./reset.sh
```

2. Set up your environment variables

```
cp .env.example .env
```

Edit accordingly

3. Install dependencies

```
pip install -r requirements.txt
```

The following is a "quick test" to see if the basics are working

Run the consumer:
   ```bash
   python kafka-consumer-pydantic.py
   ```
Run the main processor:
   ```bash
   python kafka-in-llm-out.py
   ```
Run the producer to send messages:
   ```bash
   python kafka-producer-pydantic.py
   ```

## End to End Demo

### Intake 

```bash
python -m intake.file-intake
```

```bash
 kcat -C -b localhost:9092 -t intake
```

### Structured

```bash
python -m structure.message-structure
```

```bash
kcat -C -b localhost:9092 -t structured
```

### Guardian

```bash
python -m guardian.message-guardian
```

```bash
kcat -C -b localhost:9092 -t cleared
```

### Customer

```bash
python -m customer.customer-lookup
```

```bash
kcat -C -b localhost:9092 -t ready
```


### Router

```bash
python -m router.message-router
```

```bash
kcat -C -b localhost:9092 -t support
```

```bash
kcat -C -b localhost:9092 -t finance
```

```bash
kcat -C -b localhost:9092 -t website
```

### Review

### Fire

**Drag and drop a file to "intake" directory**



## Debugging

What models are available at the endpoint:

```
curl $INFERENCE_SERVER_URL/models \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json"
```

Inference check

```
curl -sS $INFERENCE_SERVER_URL/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d "{
     \"model\": \"$MODEL_NAME\",
     \"messages\": [{\"role\": \"user\", \"content\": \"Who is Burr Sutter?\"}],
     \"temperature\": 0.0
   }" | jq -r '.choices[0].message.content'
```

## Error Handling

The system includes robust error handling:
- Failed messages are routed to a review topic
- Errors are logged with detailed information
- System maintains processing despite individual message failures

## Logging

The application uses Python's logging module with:
- Timestamp
- Log level
- Detailed message information
- Processing status updates

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE.txt](LICENSE.txt) file for details. 