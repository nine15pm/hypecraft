from datetime import date

#date time related
LOCAL_TZ = 'America/Los_Angeles'

#Shared paths
PATH_POSTS_CSV = 'data/posts_'+ date.today().strftime('%m-%d') + '.csv'
PATH_STORIES_CSV = 'data/stories_' + date.today().strftime('%m-%d') + '.csv'
PATH_TOPIC_HIGHLIGHTS_CSV = 'data/topic_highlights_' + date.today().strftime('%m-%d') + '.csv'

#Web scrape
REDDIT_HOSTNAMES = [
    '.reddit.com',
    '//reddit.com',
    '.redd.it',
    '//redd.it',
    '.redditmedia.com'
    '//redditmedia.com'
]
WEB_SCRAPE_UNSUPPORTED_HOSTS = [
    '.x.',
    '//x.',
    '.youtube.',
    '//youtube.',
    '.youtu.be',
    '//youtu.be',
    '.yt.be',
    '//yt.be',
    '.twitter.',
    '//twitter.',
    '//dubz.',
    '.dubz.link',
    '//imgur.'
]