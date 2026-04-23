import google.generativeai as genai

genai.configure(api_key="AIzaSyC4gZITI-MzNghAeMlyN4SoEslUgmQlZlE")

print("Trying to list models...")
models = list(genai.list_models())

for m in models:
    print(m.name)