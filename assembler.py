#Get summaries, gen headline, package into html for email
def prepNewsBlock(file):
    posts = utils.loadJSON(file)
    output = ''
    for post in posts:
        summary = post['ml_summary']
        link = post['post_link']
        headline = generateHeadline(summary, content_type='news')
        output = output + '<h3><b><pre>' + headline + '</pre></b></h3>' + '<p><pre>' + summary + '</pre></p>' + '<a href="' + link + '">Read more</a><br><br></p>'
    return output

def assembleNewsBlock(topic):
    pass

#Assemble newsletter
n_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

f1_message = prepRedditSummaries(PATH_POSTS_REDDIT)
semiconductors_message = prepSubstackSummaries(PATH_POSTS_SUBSTACK)

newsletter_html = f'''
<html>
  <body>
    <h1><b>NEWSLETTER V0.0.3 TEST</b></h1>
    <p><pre>{n_time}</pre></p>
    <h2>FORMULA 1 🏎️</h2>
    {f1_message}
    <p><br><br><i>Built with LLAMA 3. Definitely NOT sent with Beehiiv.</i></p>
  </body>
</html>
'''