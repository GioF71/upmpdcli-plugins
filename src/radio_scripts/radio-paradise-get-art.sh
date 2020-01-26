#!/bin/sh
# Poor example for a very basic script to retrieve the cover art. The
# Radio Paradise now.xml file actually contains much more info, but
# there has to be an example of a simple artScript (outputs cover art
# url), as opposed to metaScript (outputs full metadata json).

curl -L -s http://radioparadise.com/xml/now.xml | grep '<coverart>' | sed -e 's/<coverart>//' -e 's!</coverart>!!'
 
