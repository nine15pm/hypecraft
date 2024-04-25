import ollama as o

#Configs
SUMMARIZER_MODEL = 'phi3:instruct'
EMAIL_GEN_MODEL = 'phi3:instruct'

test = o.chat(
    model = SUMMARIZER_MODEL,
    messages = [{'role': 'user', 'content': 'Why is the sky blue?'}],
    format='json',
    stream = False
    )

print(test)