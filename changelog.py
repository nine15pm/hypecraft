#CURRENT
####################
changelog_current = 'Changelog \n\
--------------------------------\n\
- Added AI as 3rd test topic \n\
- Updated reddit content pull to support short news posts (e.g. title w/ no text) and posts with linked tweets, added tweet text parser \n\
- Fixed bug with Reddit image urls not showing properly \n\
- Fixed bug with duplicate stories being shown in Radar \n\
- Fixed bug with ordering of highlight bullets not matching ranking order \n\
--------------------------------'

#ARCHIVE
####################
changelog_06_05 = 'Changelog \n\
--------------------------------\n\
- Updated ordering logic for "Radar" section to be based on story rank score \n\
- Updated top story image to be dynamic \n\
- Added read more links to highlights bullets \n\
--------------------------------'

changelog_05_30 = 'Changelog \n\
--------------------------------\n\
- Started updating email formatting in preparation for v0.1 (first alpha) \n\
- Fixed story selection logic to not return different highlights vs. top story based on differing trend score vs. i_score rankings\n\
--------------------------------'

changelog_05_29 = 'Changelog \n\
--------------------------------\n\
- Reworked news section blocks to more traditional newsletter form to account for AMP being shit and largely unuseable \n\
- Added first version of contextual summary writing - i.e. get model to write summary that continues narrative from past stories\n\
- Adjusted logic and prompt for checking past newsletters to try get it to dedup stories that are basically repetitive but contain different info (e.g. new approach would have filtered out the top 2 F1 stories from 5-28 test newsletter) \n\
--------------------------------'

changelog_05_28 = 'Changelog \n\
--------------------------------\n\
- Updated summary generation to clean up LLM chat language from summaries \n\
- Updated topic highlights generation to have structured output to enforce bullet order match story ranking order \n\
- Fixed issue where RAG was not pulling correct past newsletter stories for comparison \n\
--------------------------------'

changelog_05_27 = 'Changelog \n\
--------------------------------\n\
- [No major changes, R&Ding AMP email components]\n\
- Updated tweet search prompt approach and reworked trend score calculation to fix issues\n\
- Tweaked ranking prompts\n\
--------------------------------'

changelog_05_25 = 'Changelog \n\
--------------------------------\n\
- Added more QA info to newsletter - (1) trend score based on tweets, (2) whether story is a repeat of past newsletter, (3) common stories from past newsletter via RAG\n\
- Updated ranking prompts and added topic-specific ranking rubric \n\
- Implemented trend score to use in future ranking update, calculated using views/likes of top tweets about news story (LLM gen search query --> tweets API) \n\
- Implemented RAG-based filtering to (1) check if story was already featured in previous newsletter and (2) check if there is any new info, if no new info then filter out \n\
--------------------------------'

changelog_05_24 = 'Changelog \n\
--------------------------------\n\
- Added top 5 retrieved past stories and similarity scores to QA search quality \n\
- Implemented search part of RAG, added pipeline steps to gen embeddings for story and post summaries and save in vector DB \n\
- Updated example themes for crypto prompts based on meeting \n\
- Fixed bug with deduping RSS feed posts \n\
--------------------------------'

changelog_05_23 = 'Changelog \n\
--------------------------------\n\
- [Not much besides slight prompt tweaks, working on implementing RAG] \n\
--------------------------------'

changelog_05_22 = 'Changelog \n\
--------------------------------\n\
- Reworked theme drafting and grouping to new prompting strategy to try and improve consistency and reduce obvious errors (LLAMA brainstorms 10 theme options, repeat 3x --> give options to GPT-4o to analyze and select best 3-5 --> self-check and edit) \n\
- Fixed bug with posts within feed not deduping properly \n\
- Prayed that tomorrows news pull doesnt break all the prompts 😰\n\
--------------------------------'

changelog_05_21 = 'Changelog \n\
--------------------------------\n\
- Set up barebones AMP email for easier QA format and to allow for future testing of UX interactions \n\
- Updated grouping/ranking pipeline to use themes and switched model to GPT-4o \n\
- Added new step in pipeline where model re-writes scraped post headlines to avoid confusing noisy garbage headlines in later steps (grouping, ranking, etc.) \n\
- Updated all grouping prompts to full chain of thought output + 2 step prompt (draft, revise), added logic to prevent exceeding token window \n\
- Fixed some bugs with web scrape \n\
--------------------------------'

changelog_05_14 = 'Changelog \n\
--------------------------------\n\
- Reworked story grouping to avoid grouping unrelated posts into a story \n\
- Updated story scoring/ranking prompt based on learnings from improving grouping prompt \n\
- Tweaked topic highlights prompt to prioritize more important bullets and 1 bullet per story (hopefully) \n\
- Fixed some bugs with newsletter assembly \n\
--------------------------------'

changelog_05_13 = 'Changelog \n\
--------------------------------\n\
- Trying slightly different prompt for topic highlights to (hopefully) generate bullet points, because YOLO \n\
- Showing model-output relevance score (0-100) beside each headline for QA purposes \n\
- Restricting topic highlights to max top 5 posts, based on the model relevance score (showing beside each headline if story would be cut) \n\
- Fixed bugs with deduping posts based on post title, URL, text \n\
- Added 2 AI subreddits to stress test, expose issues \n\
--------------------------------'

changelog_05_12 = 'Changelog \n\
--------------------------------\n\
- Updated story summary logic to use up to 3 posts for the summary. If story has more than 3 posts, choose 1 newest, 1 most text, 1 most likes. \n\
- Tweaked model prompt when summarizing stories with multiple posts. Focus on more important takeaways for fans vs. unimportant details or other narratives. \n\
- Implemented links under each story summary (shows up to 3 links corresponding to 3 posts). \n\
- Added a step for model to rank/sort available stories (using placeholder prompt), then put them in newsletter in order \n\
- Added crypto category with r/cryptocurrency and CoinDesk as feeds to stress test the system \n\
--------------------------------'

changelog_05_11 = 'Changelog \n\
--------------------------------\n\
- Updated prompt for headline generation to be less sensational and explicitly instruct to not include quotes (was hallucinating quotes) \n\
- Updated ordering of stories in news block to order stories based on number of associated posts. \n\
- Added logic to check new posts vs. existing saved posts in DB to avoid duplicates (e.g. reddit post links to same article as pulled from RSS feed) \n\
--------------------------------'