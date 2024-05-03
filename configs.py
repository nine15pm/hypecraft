from datetime import date

#Shared paths
PATH_STORIES = 'data/stories_' + date.today().strftime('%m-%d') + '.json'
PATH_STORIES_CSV = 'data/stories_test_' + date.today().strftime('%m-%d') + '.csv'