# -*- coding: utf-8 -*-
"""
This bot runs as FPCBot on wikimedia commons
It implements vote counting and supports
moving the finished nomination to the archive.

Programmed by Daniel78 at Commons.

It adds the following commandline arguments:

-test             Perform a testrun against an old log

-close            Close and add result to the nominations

-info             Just print the vote count info about the current nominations

"""

# TODO: catch exceptions

import wikipedia, re, datetime, sys

candPrefix = "Commons:Featured picture candidates/"


class Candidate():
    """
    This is one feature picture candidate.

    TODO:
    * How to detect edits (multi image nomination) ?
      imagelinks() is no good it, there might be links that are not nominations

    """

    def __init__(self, page):
        """page is a wikipedia.Page object"""
        self.page          = page
        self._oppose       = 0
        self._support      = 0
        self._neutral      = 0
        self._unknown      = 0
        self._votesCounted = False
        self._featured     = False
        self._daysOld      = -1
        self._creationTime = None
        self._striked      = None

    def printAllInfo(self):
        """
        Console output of all information sought after
        """
        self.countVotes()
        wikipedia.output("%s: S:%02d(-%02d) O:%02d(-%02d) N:%02d U:%02d D:%02d Se:%d Im:%02d W:%s (%s)" % 
                         ( self.cutTitle(),
                           self._support,self._striked[0],self._oppose,self._striked[1],
                           self._neutral,self._unknown,
                           self.daysOld(),self.sectionCount(),
                           self.imageCount(),self.isWithdrawn(),
                           self.statusString()),
                         toStdout = True)


    def countVotes(self):
        """
        Counts all the votes for this nomnination
        and subtracts eventual striked out votes
        """

        if self._votesCounted:
            return

        text = self.page.get()
        self._support = len(re.findall(SupportR,text)) 
        self._oppose  = len(re.findall(OpposeR,text))
        self._neutral = len(re.findall(NeutralR,text))

        self.findStrikedOutVotes()
        self._support -= self._striked[0]
        self._oppose  -= self._striked[1]
        self._neutral -= self._striked[2]

        self._votesCounted = True

    def findStrikedOutVotes(self):
        """
        We should not count striked out votes so 
        find them and reduce the counts.
        """
        
        if self._striked:
            return self._striked

        text = self.page.get()
        s_support = len(re.findall(StrikedOutSupportR,text))
        s_oppose  = len(re.findall(StrikedOutOpposeR,text))
        s_neutral = len(re.findall(StrikedOutNeutralR,text))

        self._striked = (s_support,s_oppose,s_neutral)
        return self._striked
        

    def isWithdrawn(self):
        """Withdrawn nominations should not be counted"""
        return len(re.findall(WithdrawnR,self.page.get()))

    def isFPX(self):
        """Page marked with FPX template"""
        return len(re.findall(FpxR,self.page.get()))

    def closePage(self):
        """
        Will add the voting results to the page if it is finished.
        If it was, True is returned else False
        """
        if not self.isDone():
            return False

        if self.imageCount() > 1:
            wikipedia.output("\"%s\" contains multiple images, ignoring" % self.page.title(),toStdout=True)
            return False

        if self.isWithdrawn():
            wikipedia.output("\"%s\" withdrawn, currently ignoring" % self.page.title(),toStdout=True)
            return False

        if self.isFPX():
            wikipedia.output("\"%s\" contains FPX, currently ignoring" % self.page.title(),toStdout=True)
            return False

        self.countVotes()

        result = "\n\n{{FPC-results-ready-for-review|support=%d|oppose=%d|neutral=%d|featured=%s|sig=~~~~}}" % \
            (self._support,self._oppose,self._neutral,"yes" if self.isFeatured() else "no")
            
        old_text = self.page.get()
        new_text = old_text + result
        
        # Show the diff
        wikipedia.output(u"\n\n>>> \03{lightpurple}%s\03{default} <<<"
                         % self.page.title())
        wikipedia.showDiff(old_text, new_text)

        choice = wikipedia.inputChoice(
            u'Do you want to accept these changes?',
            ['Yes', 'No', "Quit"],
            ['y', 'N', 'q'], 'N')

        if choice == 'y':
            wikipedia.output("Would have commited, but not implemented",toStdout=True)
        elif choice == 'q':
            wikipedia.output("Aborting.",toStdout=True)
            sys.exit(0)
        else:
            wikipedia.output("Changes ignored",toStdout=True)
        
        return True

        
    def creationTime(self):
        """
        Find the time that this candidate were created
        If we can't find the creation date, for example due to 
        the page not existing we return now() such that we
        will ifgnore this nomination as too young.
        """
        if self._creationTime:
            return self._creationTime

        history = self.page.getVersionHistory(reverseOrder=True,revCount=1)
        if not history:
            wikipedia.output("Could not retrieve history for '%s', returning now()" % self.page.title(),toStdout=True)
            return datetime.datetime.now()

        m = re.match(DateR,history[0][1].lower())
        self._creationTime = datetime.datetime(int(m.group(5)),
                                               Month[m.group(4)],
                                               int(m.group(3)),
                                               int(m.group(1)),
                                               int(m.group(2)))
        return self._creationTime
        

    def statusString(self):
        """
        A nomination can have three statuses:
         * Featured
         * Not featured
         * Active  ( not old enough )
        """
        if self.isIgnored():
            return "Ignored"
        elif self.isWithdrawn():
            return "Withdrawn"
        elif not self.isDone():
            return "Active"
        else:
            return "Featured" if self.isFeatured() else "Not featured"

    def daysOld(self):
        """Find the number of days this nomination has existed"""

        if self._daysOld != -1:
            return self._daysOld

        delta = datetime.datetime.now() - self.creationTime()
        self._daysOld = delta.days
        return self._daysOld

    def isDone(self):
        """
        Checks if a nomination can be closed
        """
        return self.daysOld() >= 9

    def isFeatured(self):
        """
        Find if an image can be featured.
        Does not check the age, it needs to be
        checked using isDone()
        """
        
        if self.isWithdrawn():
            return False

        if not self._votesCounted:
            self.countVotes()

        return self._support >= 5 and \
            (self._support >= 2*self._oppose)
    

    def isIgnored(self):
        """Some nominations currently require manual check"""
        return self.imageCount() > 1

    def sectionCount(self):
        """Count the number of sections in this candidate"""
        text = self.page.get()
        return len(re.findall(SectionR,text))

    def imageCount(self):
        """Count the number of images that are displayed"""
        text = self.page.get()
        return len(re.findall(ImagesR,text))

    def existingResult(self):
        """
        Will scan this nomination and check whether it has
        already been closed, and if so parses for the existing
        result.
        The reuturn value is a list of tuples, and normally
        there should only be one such tuple. The tuple
        contains four values:
        support,oppose,neutral,(featured|not featured)
        """
        text = self.page.get()
        return re.findall(PreviousResultR,text)

    def compareResultToCount(self):
        """
        If there is an existing result we will compare
        it to a new vote count made by this bot and 
        see if they match. This is for testing purposes
        of the bot and to find any incorrect old results.
        """
        text = self.page.get()
        res = self.existingResult()

        if self.isWithdrawn():
            wikipedia.output("%s: (ignoring, was withdrawn)" % self.cutTitle(),toStdout=True)
            return

        elif self.isFPX():
            wikipedia.output("%s: (ignoring, was FPXed)" % self.cutTitle(),toStdout=True)
            return

        elif not res:
            wikipedia.output("%s: (ignoring, has no results)" % self.cutTitle(),toStdout=True)
            return

        elif len(res) > 1:
            wikipedia.output("%s: (ignoring, has several results)" % self.cutTitle(),toStdout=True)
            return

        # We have one result, so make a vote count and compare
        old_res = res[0]
        was_featured = (old_res[3] == u'featured')
        ws = int(old_res[0])
        wo = int(old_res[1])
        wn = int(old_res[2])
        self.countVotes()

        if self._support == ws and self._oppose == wo and self._neutral == wn and was_featured == self.isFeatured():
            status = "OK"
        else:
            status = "FAIL"

        # List info to console
        wikipedia.output("%s: S%02d/%02d O:%02d/%02d N%02d/%02d F%d/%d (%s)" % (self.cutTitle(),
                                                                                self._support,ws,
                                                                                self._oppose ,wo,
                                                                                self._neutral,wn,
                                                                                self.isFeatured(),was_featured,
                                                                                status),toStdout=True)

    def cutTitle(self):
        """Returns a fixed with title"""
        return re.sub(PrefixR,'',self.page.title())[0:50].ljust(50)


def findCandidates(page_url):
    """This finds all candidates on the main FPC page"""

    page = wikipedia.Page(wikipedia.getSite(), page_url)

    candidates = []
    templates = page.getTemplates()
    for template in templates:
        title = template.title()
        if title.startswith(candPrefix):
            #wikipedia.output("Adding '%s'" % title, toStdout = True)
            candidates.append(Candidate(template))
        else:
            pass
            #wikipedia.output("Skipping '%s'" % title, toStdout = True)
    return candidates


# Exact description about what needs to be done with a closed nomination
#
# 1. Check whether the count is verified or not
# 2. If verified and featured:
#    * Add page to 'Commons:Featured pictures, list'
#    * Add to subpage of 'Commons:Featured pictures, list'
#    * Add {{Assessments|com=1}} or just the parameter if the template is already there 
#        to the picture page (should also handle subpages)
#    * Add the picture to the 'Commons:Featured_pictures/chronological/current_month'
#    * Add the template {{FPpromotion|File:XXXXX.jpg}} to the Talk Page of the nominator.
# 3. If featured or not move it from 'Commons:Featured picture candidates/candidate list'
#    to the log, f.ex. 'Commons:Featured picture candidates/Log/August 2009'

# Data and regexps used by the bot
Month  = { 'january':1, 'february':2, 'march':3, 'april':4, 'may':5, 'june':6, 'july':7, 'august':8, 'september':9, 'october':10, 'november':11, 'december':12 }
DateR = re.compile('(\d\d):(\d\d), (\d{1,2}) ([a-z]+) (\d{4})')

# List of valid templates
# They are taken from the page Commons:Polling_templates and some common redirects
support_templates = (u'[Ss]upport',u'[Pp]ro',u'[Ss]im',u'[Tt]ak',u'[Ss]í',u'[Pp]RO',u'[Ss]up',u'[Yy]es',u'[Oo]ui',u'[Kk]yllä', # First support + redirects
                     u'падтрымліваю',u'[Aa] favour',u'[Pp]our',u'[Tt]acaíocht',u'[Cc]oncordo',u'בעד', 
                     u'[Ss]amþykkt',u'支持',u'찬성',u'[Ss]for',u'за',u'[Ss]tödjer',u'เห็นด้วย',u'[Dd]estek')
oppose_templates  = (u'[Oo]ppose',u'[Kk]ontra',u'[Nn]ão',u'[Nn]ie',u'[Mm]autohe',u'[Oo]pp',u'[Nn]ein',u'[Ee]i', # First oppose + redirect
                     u'[Cс]упраць',u'[Ee]n contra',u'[Cc]ontre',u'[Ii] gcoinne',u'[Dd]íliostaigh',u'[Dd]iscordo',u'נגד',u'á móti',u'反対',u'除外',u'반대',
                     u'[Mm]ot',u'против',u'[Ss]tödjer ej',u'ไม่เห็นด้วย',u'[Kk]arsi',u'FPX contested')
neutral_templates = (u'[Nn]eutral?',u'[Oo]partisk',u'[Nn]eutre',u'[Nn]eutro',u'נמנע',u'[Nn]øytral',u'中立',u'Нэўтральна',u'[Tt]arafsız',u'Воздерживаюсь',
                     u'[Hh]lutlaus',u'중립',u'[Nn]eodrach',u'เป็นกลาง','[Vv]n')

# 
# Compiled regular expressions follows
#

# Used to remove the prefix and just print the file names
# of the candidate titles.
PrefixR = re.compile("%s(removal/)?([Ff]ile|[Ii]mage)?:" % candPrefix)

# Looks for result counts, an example of such a line is:
# '''result:''' 3 support, 2 oppose, 0 neutral => not featured.
#
PreviousResultR = re.compile('\'\'\'result:\'\'\'\s+(\d+)\s+support,\s+(\d+)\s+oppose,\s+(\d+)\s+neutral\s*=>\s*((?:not )?featured)',re.MULTILINE)

# Is whitespace allowed at the end ?
SectionR = re.compile('^={1,4}.+={1,4}\s*$',re.MULTILINE)
# Voting templates
SupportR = re.compile("{{\s*(?:%s)(\|.*)?\s*}}" % "|".join(support_templates),re.MULTILINE)
OpposeR  = re.compile("{{\s*(?:%s)(\|.*)?\s*}}" % "|".join( oppose_templates),re.MULTILINE)
NeutralR = re.compile("{{\s*(?:%s)(\|.*)?\s*}}" % "|".join(neutral_templates),re.MULTILINE)
# Striked out votes 
StrikedOutSupportR = re.compile("<s>.*{{\s*(?:%s)(\|.*)?\s*}}.*</s>" % "|".join(support_templates),re.MULTILINE)
StrikedOutOpposeR  = re.compile('<s>.*{{\s*(?:%s)(\|.*)?\s*}}.*</s>' % "|".join( oppose_templates),re.MULTILINE)
StrikedOutNeutralR = re.compile('<s>.*{{\s*(?:%s)(\|.*)?\s*}}.*</s>' % "|".join(neutral_templates),re.MULTILINE)
# Finds if a withdraw template is used
# This template has an optional string which we
# must be able to detect after the pipe symbol
WithdrawnR = re.compile('{{\s*[wW]ithdraw\s*(\|.*)?}}',re.MULTILINE)
# Nomination that contain the fpx template
FpxR = re.compile('{{\s*FPX(\|.*)?}}',re.MULTILINE)
# Counts the number of displayed images
ImagesR = re.compile('\[\[(File|Image):.+\]\]',re.MULTILINE)

def main(*args):

    fpcTitle = 'Commons:Featured picture candidates/candidate list'
    testLog = 'Commons:Featured_picture_candidates/Log/January_2009'

    worked = False

    for arg in wikipedia.handleArgs(*args):
        worked = True
        if arg == '-test':
            for candidate in findCandidates(testLog):
                try:
                    candidate.compareResultToCount()
                except wikipedia.IsRedirectPage:
                    pass
        elif arg == '-close':
            for candidate in findCandidates(fpcTitle):
                candidate.closePage()
        elif arg == '-info':
            for candidate in findCandidates(fpcTitle):
                try:
                    candidate.printAllInfo()
                except wikipedia.NoPage:
                    wikipedia.output("No such page '%s'" % candidate.page.title(), toStdout = True)
                    pass
        else:
            wikipedia.output("Warning - unknown argument '%s', see -help." % arg, toStdout = True)

    if not worked:
        wikipedia.output("Warning - you need to specify an argument, see -help.", toStdout = True)
            

if __name__ == "__main__":
    try:
        main()
    finally:
        wikipedia.stopme()

