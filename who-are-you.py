from dotenv import load_dotenv
from openai import OpenAI

import os

load_dotenv()

# .env points to the several model servers and models

question = "who is Burr Sutter?"

# ---------------------------------
MODEL = "STRUCTURE"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
MODEL = "GUARDIAN"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
MODEL = "ROUTER"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
MODEL = "SUPPORT"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
MODEL = "WEBSITE"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
MODEL = "OPPORTUNITY"
structure_client = OpenAI(
    api_key=os.getenv(f"{MODEL}_API_KEY"),
    base_url=os.getenv(f"{MODEL}_SERVER_URL")
)

model_name = os.getenv(f"{MODEL}_MODEL_NAME")

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)

# ---------------------------------
model_name="llama3.2:3b-instruct-fp16"
structure_client = OpenAI(
    api_key="none",
    base_url="http://localhost:11434/v1"
)

completion = structure_client.chat.completions.create(
    model= model_name,
    messages=[
        {"role": "system", "content": "You're a helpful assistant."},
        {
            "role": "user",
            "content": question,
        },
    ],
    temperature=0.0, 
)

response = completion.choices[0].message.content

print(f"\n\n{model_name}")
print(response)
print(f"{model_name}")
print("-" * 40)
