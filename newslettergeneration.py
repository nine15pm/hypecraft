import db
import configs
import utils
import emailer
import changelog
import RAG
from pytz import timezone
from datetime import datetime, time

#HELPER FUNCTIONS
##############################################################################################
#Record usage of story and posts in newsletter
def recordUsage(stories:list[dict], newsletter_date):
    story_updates = []
    post_updates = []
    story_vectordb_ids = []
    story_vectordb_update = {
        'used_in_newsletter': True,
        'newsletter_date': newsletter_date
    }
    for story in stories:
        story_updates.append({
            'story_id': story['story_id'],
            'used_in_newsletter': True,
            'newsletter_date': newsletter_date
        })
        story_vectordb_ids.append(story['story_id'])
        for post_id in story['posts_summarized']:
            post_updates.append({
                'post_id': post_id,
                'used_in_newsletter': True,
                'newsletter_date': newsletter_date
            })
    RAG.updateStoriesPayload(point_ids=story_vectordb_ids, payload_fields=story_vectordb_update)
    db.updateStories(story_updates)
    db.updatePosts(post_updates)

def getTopPostLink(post_ids):
    posts = db.getPosts(filters={'post_id': post_ids})
    most_text = max(posts, key=lambda post:len(post['external_parsed_text'] if post['external_parsed_text'] is not None else post['post_text']))
    return most_text['external_link'] if most_text['external_link'] is not None else most_text['post_link']

#HTML UNIT CONSTRUCTORS
##############################################################################################
def ampLink(text, url):
    return f'<a href="{url}" class="link">{text}</a>'

def storyUnit(tag:str, headline:str, body:str, links:list, rag=False, rag_items=[]):
    links_html = ''
    for i, link in enumerate(links):
        links_html = links_html + ampLink(text=f'Link {i}', url=link)
    
    #Show RAG results for QA
    if rag:
        rag_string = ''
        for item in rag_items:
            rag_string = rag_string + f'- [[Past newsletter: {item['newsletter_date']}] {item['headline_ml']}\n'
    else:
        rag_string=''

    output_html = f'''
    <div class="story-card">
        <div class="story-card-wrapper">
            <div class="story-card-content">
                <span class="tag">{tag}</span>
                <h4 class="heading-unit"><b>{headline}</b></h4>
                <p class="paragraph">{body}</p>
                <div class="story-card-links">
                    {links_html}
                </div>
                <div>
                    <p class="small-text">
                        {utils.linebreaksHTML(rag_string)}
                    </p>
                </div>
            </div>
        </div>
    </div>
    '''
    return output_html

def themeUnit(headline:str, body:str):
    output_html = f'''
    <div class="story-card">
        <div class="story-card-wrapper">
            <div class="story-card-content">
                <h4 class="heading-unit"><b>{headline}</b></h4>
                <p class="paragraph">{body}</p>
            </div>
        </div>
    </div>
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
def constructTopStoriesBlock(topic_id, min_datetime, newsletter_date):
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    top_story_ids = db.getNewsSections(min_datetime=min_datetime, filters={'topic_id': topic_id})[0]['top_stories']
    top_stories = db.getStories(filters={'story_id': top_story_ids})
    top_stories_html = ''

    for story in top_stories:
        #get links of summarized posts
        posts = db.getPostLinksForStory(story['posts_summarized'])
        links = []
        for post in posts:
            if post['external_link'] == None or post['external_link'] == '':
                link = post['post_link']
            else:
                link = post['external_link']
            links.append(link)

        #Get QA info to attach
        ml_score = f' (ML score: {story['daily_i_score_ml']})'
        trend_score = f' (Trend score: {round(story['trend_score'])})'
        past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

        #optional rag
        rag = True
        rag_list = db.getStories(filters={'story_id': story['past_common_stories']})

        headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
        tag = [theme['theme_name_ml'] for theme in themes if theme['theme_id'] == story['theme_id']][0]

        top_stories_html += storyUnit(tag=tag, headline=headline, body=story['summary_ml'], links=links, rag=rag, rag_items=rag_list)
    
    output_html = f'''
    <div class="block-stories">
      <h3 class="heading-block"><b>Radar</b></h3>
      {top_stories_html}
    </div>
    '''
    #record usage of stories and posts in newsletter
    recordUsage(stories=top_stories, newsletter_date=newsletter_date)

    return output_html

#Prep a Radar block of lower ranked news stories grouped by theme
def constructRadarBlock(topic_id, min_datetime, newsletter_date):
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    radar_html = ''

    for theme in themes:
        if theme['radar_summary_ml'] is not None:
            assembled_summary = ''
            for part in theme['radar_summary_ml']:
                story = db.getStories(filters={'story_id': part['story_id']})[0]
                #record usage of stories and posts in newsletter
                recordUsage(stories=[story], newsletter_date=newsletter_date)
                assembled_summary += part['part'] + f' [{ampLink('link', url=getTopPostLink(story['posts_summarized']))}] '
            
            radar_html += themeUnit(headline=theme['theme_name_ml'], body=assembled_summary)
    
    output_html = f'''
    <div class="block-stories">
      <h3 class="heading-block"><b>Radar</b></h3>
      {radar_html}
    </div>
    '''

    return output_html

#Prep the QA sections showing all stories
def constructNewsQABlock(topic_id, min_datetime):
    themes = db.getThemesForTopic(topic_id, min_datetime=min_datetime)
    units = []
    
    #get top stories and sort
    top_story_ids = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]['stories']
    top_stories = db.getStories(min_datetime=min_datetime, filters={'story_id': top_story_ids})
    top_stories = sorted(top_stories, key=lambda story: story['daily_i_score_ml'], reverse=True)

    #get remaining stories and sort
    all_stories = db.getStoriesForTopic(topic_id=topic_id, min_datetime=min_datetime)
    all_stories = [story for story in all_stories if story['story_id'] not in top_story_ids]
    unused_stories = all_stories if all_stories != [] else []

    child = ''
    parent = f'''
    <h4 class="accordion-title">
        <b>[QA: Top ranked stories]</b>
    </h4>
    '''

    for story in top_stories:
        #get links of summarized posts
        posts = db.getPostLinksForStory(story['posts_summarized'])
        links = []
        for post in posts:
            if post['external_link'] == None or post['external_link'] == '':
                link = post['post_link']
            else:
                link = post['external_link']
            links.append(link)

        #Get QA info to attach
        ml_score = f' (ML score: {story['daily_i_score_ml']})'
        trend_score = f' (Trend score: {round(story['trend_score'])})'
        past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

        #optional rag
        rag = True
        rag_list = db.getStories(filters={'story_id': story['past_common_stories']})
        
        headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
        tag = [theme['theme_name_ml'] for theme in themes if theme['theme_id'] == story['theme_id']][0]

        child = child + storyUnit(tag=tag, headline=headline, body=story['summary_ml'], links=links, rag=rag, rag_items=rag_list)
        child = f'<div>{child}</div>'
            
    units.append((parent, child))

    #add unused stories accordion section if applicable
    if unused_stories != []:
        parent = f'''
        <h4 class="accordion-title">
            <b>[QA: Lower ranked stories in Radar section]</b>
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

            #Get QA info to attach
            ml_score = f' (ML score: {story['daily_i_score_ml']})' if story['daily_i_score_ml'] is not None else ' (ML score: N/A)'
            trend_score = f' (Trend score: {round(story['trend_score'])})' if story['trend_score'] is not None else ' (Trend score: N/A)'
            past_newsletter = f' (Past repeat: {story['past_newsletter_repeat']})'

            headline = story['headline_ml'] + ml_score + trend_score + past_newsletter
            tag = [theme['theme_name_ml'] for theme in themes if theme['theme_id'] == story['theme_id']][0]
            child = child + storyUnit(tag=tag, headline=headline, body=story['summary_ml'], links=links)
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
def constructHighlightBlock(topic_id, min_datetime, newsletter_date):
    bullets_list_sorted = db.getTopicHighlights(min_datetime=min_datetime, filters={'topic_id':topic_id})[0]['summary_bullets_ml']

    #construct bullets html
    bullets_html = ''
    for bullet in bullets_list_sorted:
        bullets_html += f'<li>{bullet['bullet']}</li>'

    output_html = f'''
    <div class="block-spotlight">
      <h3 class="heading-block"><b>Highlights</b></h3>
      <p class="paragraph"><ol>{bullets_html}</ol></p>
    </div>
    '''
    #record usage of stories and posts in newsletter
    stories_used_ids = db.getNewsSections(min_datetime=min_datetime, filters={'topic_id': topic_id})[0]['highlight_stories']
    stories_used = db.getStories(filters={'story_id': stories_used_ids})
    recordUsage(stories=stories_used, newsletter_date=newsletter_date)

    return output_html

#SECTION CONSTRUCTORS
##############################################################################################
#Prep the newsletter main title
def constructTopHeaderSection(newsletter_title):
    n_date = datetime.strftime(datetime.now(), "%Y-%m-%d %I:%M")
    output_html = f'''
    <header class="section-topheader">
        <h1><b>{newsletter_title}</b></h1>
        <div class="date-div">
            <p class="paragraph"><i>{n_date}</i></p>
        </div>
    </header>
    '''
    return output_html

def constructChangelogSection(changelog):
    output_html = f'''
    <div class="section-changelog">
        <h2 class="heading-section">Changelog</h2>
        <p class="paragraph">{utils.linebreaksHTML(changelog)}</p>
    </div>
    '''
    return output_html

def constructFooterSection(footer_text):
    output_html = f'''
    <footer class="section-footer">
        <p class="paragraph small-text">{footer_text}</p>
    </footer>
    '''
    return output_html

#Combine several blocks (e.g. topic highlights, news stories) into an overall topic section
def constructTopicSection(topic_id, min_datetime, newsletter_date, has_highlight=True, has_top_stories=True, has_radar=True, has_news_QA=True):
    #get topic heading
    topic = db.getTopics(filters={'topic_id': topic_id})[0]
    topic_heading = f'''<h2>{topic['topic_email_name']}</h2>'''

    #construct topic highlights block
    highlight_block = constructHighlightBlock(topic_id, min_datetime, newsletter_date) if has_highlight else ''

    #construct top stories block
    top_stories_block = constructTopStoriesBlock(topic_id, min_datetime, newsletter_date) if has_top_stories else ''

    #construct radar block
    radar_block = constructRadarBlock(topic_id, min_datetime, newsletter_date) if has_radar else ''
    
    #construct QA block
    news_QA_block = constructNewsQABlock(topic_id, min_datetime) if has_news_QA else ''

    output_html = f'''
    <div class="section-topic">
        <h2 class="heading-section">{topic_heading}</h2>
        {highlight_block}
        {top_stories_block}
        {radar_block}
        {news_QA_block}
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
today_start = datetime.combine(datetime.today(), time.min).astimezone(timezone(configs.LOCAL_TZ))
newsletter_date = datetime.today()
topics = [{'topic_id': 1}]
title = 'HYPECRAFT V0.0.4 TEST'
footer_text = f'''🫶 Written for you with love by Hypecraft on {datetime.strftime(newsletter_date, "%A, %B %m")}. Powered by Lllama 3.'''
recipients1 = ['maintainer@example.com']
recipients2 = ['maintainer@example.com', 'contributor@example.com']

header = constructTopHeaderSection(title)
log = constructChangelogSection(changelog.changelog_current)
main_content = ''
for topic in topics:
    main_content = main_content + constructTopicSection(topic_id=topic['topic_id'], min_datetime=today_start, newsletter_date=newsletter_date)
footer = constructFooterSection(footer_text=footer_text)
newsletter_html = wrapEncodeHTML(body_html=header + log + main_content + footer, template_path=PATH_EMAIL_TEMPLATE)
#print(newsletter_html)
emailer.sendNewsletter(subject=title, recipients=recipients1, content_html=newsletter_html)