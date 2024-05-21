#date time related
LOCAL_TZ = 'America/Los_Angeles'

#Web scrape
WEBCACHE_URL = 'http://webcache.googleusercontent.com/search?q=cache:'
TWITTER_OEMBED_URL = 'https://publish.twitter.com/oembed?url='
REDDIT_HOSTNAMES = [
    '.reddit.com',
    '//reddit.com',
    '.redd.it',
    '//redd.it',
    '.redditmedia.com'
    '//redditmedia.com'
]
TWITTER_HOSTNAMES = [
    '.twitter.',
    '//twitter.',
    '.x.',
    '//x.',
    '//t.'
]
WEB_SCRAPE_UNSUPPORTED_HOSTS = TWITTER_HOSTNAMES + [
    '.youtube.',
    '//youtube.',
    '.youtu.be',
    '//youtu.be',
    '.yt.be',
    '//yt.be',
    '//dubz.',
    '.dubz.link',
    '//imgur.'
]