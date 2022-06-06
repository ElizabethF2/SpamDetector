The very heavily redacted code for a bot I use to detect spam on Reddit. The parts that have anything to do with how the bot detects spam have been removed so this code can't be used as-is but the remaining code is useful as a reference, particularly to anyone working on Reddit bots or image processing. 

Items of Note:
 - bot.py includes a basic Reddit API client which only has dependencies on the standard libraries and that can be easily monkey-patched to support using any library for web requests
 - imagehash_no_numpy.py, as its name implies, reimplements dhash so that it can be used without any dependencies on numpy.

This readme is a stub. Full documentation and a license will be added in the future. See the current comments and code for info regarding setup and usage.
