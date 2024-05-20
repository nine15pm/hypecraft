import db
import configs
import emailer
import changelog
from pytz import timezone
from datetime import datetime, time, timedelta

#HTML UNIT CONSTRUCTORS
##############################################################################################
def ampLink(text, url):
    return f'<a href="{url}" class="link">{text}</a>'

def storyUnit(headline:str, body:str, links:list):
    links_html = ''
    for i, link in enumerate(links):
        links_html = links_html + ampLink(text=f'Link {i}', url=link)
    output_html = f'''
        <div class="story">
            <h4 class="heading-unit"><b>{headline}</b></h4>
            <p class="paragraph">{body}</p>
            {links_html}
        </div>
        '''
    return output_html

def themeUnit(tag:str, body:str):
    output_html = f'''
    <h4 class="theme-unit">
        <span class="tag">{tag}</span>
        <p class="paragraph">{body}</p>
    </h4>
    '''
    return output_html

def ampAccordion(units:list[tuple]):
    sections_html = ''
    for pair in units:
        parent = pair[0]
        child = pair[1]
        section = f'''
        <section>
        {parent}
        {child}
        </section>
        '''
        sections_html = sections_html + section
    output_html = f'''
    <amp-accordion animate>
        {sections_html}
    </amp-accordion>
    '''
    return output_html
    
#BLOCK CONSTRUCTORS
##############################################################################################
#Prep a news themes/stories block within a topic section
def constructNewsBlock(topic_id, top_k_stories, min_datetime):
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    units = []
    unused_stories = []
    #construct accordion section for each theme
    for theme in themes:
        stories = db.getStoriesForTheme(theme['theme_id'], min_datetime=min_datetime)
        
        #filter out Other
        if theme['theme_name_ml'] == 'Other':
            unused_stories = unused_stories + stories
            continue
        
        #sort stories based on i_score from model, take top 3, then construct units
        stories = sorted(stories, key=lambda story: story['daily_i_score_ml'], reverse=True)
        theme_score = stories[0]['daily_i_score_ml']
        if len(stories) > top_k_stories:
            unused_stories = stories[top_k_stories:]
            stories = stories[:top_k_stories]
        child = ''
        for story in stories:
            #get links of summarized posts
            posts = db.getPostLinksForStory(story['posts_summarized'])
            links = []
            for post in posts:
                if post['external_link'] == None or post['external_link'] == '':
                    link = post['post_link']
                else:
                    link = post['external_link']
                links.append(link)
            ml_score = f' (ML score: {story['daily_i_score_ml']})'
            child = child + storyUnit(headline=story['headline_ml'] + ml_score, body=story['summary_ml'], links=links)
            child = f'<div>{child}</div>'
        parent = themeUnit(tag=theme['theme_name_ml'], body=theme['summary_ml'])
        units.append((parent, child, theme_score))

    #sort units by theme with highest i score story
    units = sorted(units, key=lambda tup: tup[2])
    
    #add unused stories accordion section if applicable
    if unused_stories != []:
        parent = f'''
        <h4 class="theme-unit">
            <b>[Stories cut from newsletter]</b>
        </h4>
        '''
        child = ''
        for story in unused_stories:
            #get links of summarized posts
            posts = db.getPostLinksForStory(story['posts_summarized'])
            links = []
            for post in posts:
                if post['external_link'] == None or post['external_link'] == '':
                    link = post['post_link']
                else:
                    link = post['external_link']
                links.append(link)
            ml_score = f' (ML score: {story['daily_i_score_ml']})'
            child = child + storyUnit(headline=story['headline_ml'] + ml_score, body=story['summary_ml'], links=links)
            child = f'<div>{child}</div>'
        units.append((parent, child))
    
    #construct accordion and output
    accordion_html = ampAccordion(units)
    output_html = f'''
    <div class="block-stories">
      <h3 class="heading-block"><b>Top Stories</b></h3>
      {accordion_html}
    </div>
    '''
    return output_html

#Prep a topic highlight block within a topic section
def constructHighlightBlock(topic_id, min_datetime):
    highlight = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]
    output_html = f'''
    <div class="block-spotlight">
      <h3 class="heading-block"><b>Highlights</b></h3>
      <p class="paragraph">{highlight['summary_ml']}<br></p>
    </div>
    '''
    return output_html

#SECTION CONSTRUCTORS
##############################################################################################
#Prep the newsletter main title
def constructTopHeaderSection(newsletter_title):
    n_date = datetime.strftime(datetime.now(), "%Y-%m-%d %I:%M")
    output_html = f'''
    <div class="section-topheader">
        <h1><b>{newsletter_title}</b></h1>
        <div class="date-div">
            <p class="paragraph"><i>{n_date}</i></p>
        </div>
    </div>
    '''
    return output_html

def constructChangelogSection(changelog):
    output_html = f'''
    <div class="section-changelog">
        <h2 class="heading-section">Changelog</h2>
        <p class="paragraph">{changelog}</p>
    </div>
    '''
    return output_html

def constructFooterSection(footer_text):
    output_html = f'''
    <div class="section-footer">
        <p class="paragraph small-text">{footer_text}</p>
    </div>
    '''
    return output_html

#Combine several blocks (e.g. topic highlights, news stories) into an overall topic section
def constructTopicSection(topic_id, min_datetime, top_k_stories, has_highlight=True, has_news=True):
    #get topic heading
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic_heading = f'''<h2>{topic['topic_email_name']}</h2>'''

    #construct topic highlights block
    highlight_block = constructHighlightBlock(topic_id, min_datetime) if has_highlight else ''
    
    #construct news block
    news_block = constructNewsBlock(topic_id, top_k_stories, min_datetime) if has_news else ''

    output_html = f'''
    <div class="section-topic">
        <h2 class="heading-section">{topic_heading}</h2>
        {highlight_block}
        {news_block}
    </div>
    '''
    return output_html

#wrap constructed newsletter with html and body tags
def wrapEncodeHTML(body_html, template_path):
    with open(template_path, 'rb') as file: 
        template_html = file.read()
    template_html = template_html.decode("utf-8")
    body_end_idx = template_html.index('</body>')
    output_html = template_html[:body_end_idx] + body_html + template_html[body_end_idx:]
    return output_html

#GENERATE NEWSLETTER AND SEND
##############################################################################################
PATH_EMAIL_TEMPLATE = 'emailtemplates/amptemplate_v004.html'
today_start = datetime.combine(datetime.today(), time.min).astimezone(timezone(configs.LOCAL_TZ)) - timedelta(days=1)
topics = [{'topic_id': 1}, {'topic_id': 2}]
title = 'HYPECRAFT V0.0.4 TEST'
top_k_stories = 3
footer_text = f'''<br><br><p><small>🫶 Written for you with love by Hypecraft on {datetime.strftime(datetime.now(), "%A, %B %m")}. Powered by Lllama 3.</small></p>'''
recipients1 = ['maintainer@example.com']
recipients2 = ['maintainer@example.com', 'contributor@example.com']

header = constructTopHeaderSection(title)
log = constructChangelogSection(changelog.changelog_current)
main_content = ''
for topic in topics:
    main_content = main_content + constructTopicSection(topic_id=topic['topic_id'], top_k_stories=top_k_stories, min_datetime=today_start)
footer = constructFooterSection(footer_text=footer_text)
newsletter_html = wrapEncodeHTML(body_html=header + log + main_content + footer, template_path=PATH_EMAIL_TEMPLATE)
#print(newsletter_html)
emailer.sendNewsletter(subject=title, recipients=recipients1, content_html=newsletter_html)