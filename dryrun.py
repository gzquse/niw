from openai import OpenAI
import os

# The client will automatically look for the "OPENAI_API_KEY" variable
client = OpenAI() 

models = client.models.list()
for model in models:
    print(model.id)