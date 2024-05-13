#CURRENT
####################
changelog_current = 'Changelog \n\
--------------------------------\n\
- Updated story summary logic to use up to 3 posts for the summary. If story has more than 3 posts, choose 1 newest, 1 most text, 1 most likes. \n\
- Tweaked model prompt when summarizing stories with multiple posts. Focus on more important takeaways for fans vs. unimportant details or other narratives. \n\
- Implemented links under each story summary (shows up to 3 links corresponding to 3 posts). \n\
- Added a step for model to rank/sort available stories (using placeholder prompt), then put them in newsletter in order \n\
- Added crypto category with r/cryptocurrency and CoinDesk as feeds to stress test the system \n\
--------------------------------'

#ARCHIVE
####################
changelog_05_11 = 'Changelog \n\
--------------------------------\n\
- Updated prompt for headline generation to be less sensational and explicitly instruct to not include quotes (was hallucinating quotes) \n\
- Updated ordering of stories in news block to order stories based on number of associated posts. \n\
- Added logic to check new posts vs. existing saved posts in DB to avoid duplicates (e.g. reddit post links to same article as pulled from RSS feed) \n\
--------------------------------'