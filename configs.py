from datetime import date

#Shared paths
PATH_STORIES_CSV = 'data/stories_test_' + date.today().strftime('%m-%d') + '.csv'

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