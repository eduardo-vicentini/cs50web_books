# CS50 Books

Project to have a webapplication with books that the users can post their reviews on.

Besides the rating posted on the site, it also shows the ratings as is get by the Goodreads API.

## application

All the code base in on the file application.py. The only part that is not is the import to the database of the 5000 books in a csv, that is done by the import.py.

## Requirements

The requeirements is all on the requirements.txt.

## Own API

This application also returns a json in the url /api/ISBN, where isbn is the isbn of a book.