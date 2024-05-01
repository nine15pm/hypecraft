import requests
HF_API_URL = 'https://api-inference.huggingface.co/models/'
HF_API_KEY = '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'
HF_API_HEADERS = {
    'Authorization': f'Bearer {HF_API_KEY}'
    }
HF_MODEL = 'meta-llama/Meta-Llama-3-70B-Instruct'

def summarizeContent(content_text):
    params = {
        'temperature': 1.0,
        'truncate': 6144,
        'max_new_tokens': 2047,
        'stop': ['<|eot_id|>'],
        'stop_sequences': ['<|eot_id|>'],
        'return_full_text': False
    }
    inputs = '<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n' + content_text + '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n'
    payload = {
        'inputs': inputs,
        'parameters': params
    }
    response = requests.post(HF_API_URL + HF_MODEL, headers=HF_API_HEADERS, json=payload)
    print(response.json())

teststring = '''Your task is to write a short summary of a new blog post or article for someone who does not have time to read the full thing. Follow this general structure for the summary:\n\n

1. Start by acknowledging the new blog post or article, in a few words.\n
2. Then, briefly explain the key insights from the article. This part should be the majority of the summary.\n
3. Then, in one highlighted sentence starting with "Why this matters:" explain the main implication and why the reader should care about it.\n
4. Finally, if necessary, invite the reader to read the full article for details.\n\n

The writing style of the summary should be conversational and engaging. Use direct language and do not be verbose so it is easy to understand. Write in third person only, do NOT write in first person.\n\n

Write a summary for the following content, in 250 words or less:\n\n

Intel’s 14A Magic Bullet: Directed Self-Assembly (DSA)
How High-NA EUV can be economically viable at the 1.4nm process node

<p>Intel&#8217;s 18A node gets most of the spotlight recently &#8211; with an ongoing battle between TSMC&#8217;s and Intel&#8217;s management teams on the merits of TSMC N2 vs Intel&#8217;s 18A. However, it is 14A that will be the make-or-break node for Intel Foundry. Winning customers starts with process technology, and Intel is betting big here, but they need a generation where everyone gets comfortable. Customers will use 18A to dip their toes in the Intel waters with less critical chips that are not core to their business; if all goes well, they will look to 14A as the main process for their linchpin designs &#8211; think the largest, expensive dies like AI accelerators, CPUS, and potentially even mobile in 2027.</p><p>Intel will need to win their business to make its IDM 2.0 foundry strategy work, or else they will not have enough scale and volume to compete given their internal product business will continue to lose market share for the next few years. It simply isn&#8217;t possible to run a leading-edge foundry without multiple large, leading-edge customers.</p><div class="digest-post-embed"></div><p>Intel will be the first, by a margin of years, to adopt ASML&#8217;s high-NA EUV lithography scanners in high volume manufacturing. Both TSMC and Samsung have only ordered tools for R&amp;D. Intel, perhaps trying to correct for being late to the low-NA game, has been high-NA&#8217;s loudest and strongest champion. With the first customer-owned example now being installed in their Hillsboro fab, Intel will have a head start on R&amp;D and real-world experience with high-NA scanners.</p><p>But there is the question of economics. Our model shows that high-NA single exposure is <a href="https://www.semianalysis.com/p/asml-dilemma-high-na-euv-is-worse">more expensive than low-NA double patterning</a>.</p><p>And other chipmakers have publicly signaled that high-NA is too expensive through both their low orders and with public commentary:</p><blockquote><p>Technology itself is of no value. Only what can serve your customer.
'''

summarizeContent(teststring)