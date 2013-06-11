# vim:fileencoding=utf-8:sw=4:et

# Copyright (c) 2013 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

######################################################################
# Public API:
#
#     list_locales()
#     list_keyboards()
#     list_consolefonts()
#     language_name()
#     territory_name()
#     supports_ascii()
#
# These are the functions which do not start with an “_” in their name.
# All global functions and global variables whose name starts with an
# “_” are internal and should not be used by a user of langtable.py.
#
######################################################################

import os
import re
import logging
import gzip

import xml.parsers.expat
from xml.sax.handler import ContentHandler

# will be replaced by “make install”:
_datadir = '/usr/share/langtable'

# For the ICU/CLDR locale pattern see: http://userguide.icu-project.org/locale
# (We ignore the variant code here)
_cldr_locale_pattern = re.compile(
    # language must be 2 or 3 lower case letters:
    '^(?P<language>[a-z]{2,3}'
    # language is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +'|_[A-Z][a-z]{3}(?=$|@|_[A-Z]{2}(?=$|@))' # valid script follows
    +'|_[A-Z]{2}(?=$|@)' # valid territory follows
    +'))'
    # script must be 1 upper case letter followed by
    # 3 lower case letters:
    +'(?:_(?P<script>[A-Z][a-z]{3})'
    # script is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +'|_[A-Z]{2}(?=$|@)' # valid territory follows
    +')){0,1}'
    # territory must be 2 upper case letters:
    +'(?:_(?P<territory>[A-Z]{2})'
    # territory is only valid if
    +'(?=$|@' # locale string ends here or only options follow
    +')){0,1}')

# http://www.unicode.org/iso15924/iso15924-codes.html
_glibc_script_ids = {
    'latin': 'Latn',
    'iqtelif': 'Latn', # Tatar, tt_RU.UTF-8@iqtelif, http://en.wikipedia.org/wiki/User:Ultranet/%C4%B0QTElif
    'cyrillic': 'Cyrl',
    'devanagari': 'Deva',
}

_territories_db = {}
_languages_db = {}
_keyboards_db = {}

class territory_db_item:
    def __init__(self, names = None, locales=None, languages=None, keyboards=None, consolefonts=None, timezones=None):
        self.names = names
        self.locales = locales
        self.languages = languages
        self.keyboards = keyboards
        self.consolefonts = consolefonts
        self.timezones = timezones

class language_db_item:
    def __init__(self, iso639_1=None, iso639_2_t=None, iso639_2_b=None, names=None, locales=None, territories=None, keyboards=None, consolefonts=None, timezones=None):
        self.iso639_1 = iso639_1
        self.iso639_2_t = iso639_2_t
        self.iso639_2_b = iso639_2_b
        self.names = names
        self.locales = locales
        self.territories = territories
        self.keyboards = keyboards
        self.consolefonts = consolefonts
        self.timezones = timezones

class keyboard_db_item:
    def __init__(self, description=None, ascii=True, languages=None, territories = None, comment=None):
        self.description = description
        self.ascii  = ascii
        self.comment = comment
        self.languages = languages
        self.territories = territories

# xml.sax.handler.ContentHandler is not inherited from the 'object' class,
# 'super' keyword wouldn't work, we need to inherit it on our own
class LangtableContentHandler(ContentHandler, object):
    """
    A base class inherited from the xml.sax.handler.ContentHandler class
    providing handling for SAX events produced when parsing the langtable data
    files.

    """

    def __init__(self):
        # internal attribute used to set where the upcoming text data should be
        # stored
        self._save_to = None

    def characters(self, content):
        """Handler for the text data event."""

        if self._save_to is None:
            # don't know where to save data
            return

        # text content may split in multiple events
        old_value = getattr(self, self._save_to)
        if old_value:
            new_value = old_value + content
        else:
            new_value = content

        setattr(self, self._save_to, new_value)

class TerritoriesContentHandler(LangtableContentHandler):
    """Handler for SAX events produced when parsing the territories.xml file."""

    def __init__(self):
        super(TerritoriesContentHandler, self).__init__()

        # simple values
        self._territoryId = None

        # helper variables
        self._item_id = None
        self._item_rank = None
        self._item_name = None

        # dictionaries
        self._names = None
        self._locales = None
        self._languages = None
        self._keyboards = None
        self._consolefonts = None
        self._timezones = None

    def startElement(self, name, attrs):
        if name == u"territory":
            self._names = dict()
            self._locales = dict()
            self._languages = dict()
            self._keyboards = dict()
            self._consolefonts = dict()
            self._timezones = dict()

        # non-dict values
        elif name == u"territoryId":
            self._save_to = "_territoryId"

        # dict items
        elif name in (u"languageId", u"localeId", u"keyboardId",
                      u"consolefontId", u"timezoneId"):
            self._save_to = "_item_id"
        elif name == u"trName":
            self._save_to = "_item_name"
        elif name == u"rank":
            self._save_to = "_item_rank"

    def endElement(self, name):
        # we don't allow text to appear on the same level as elements so outside
        # of an element no text should appear
        self._save_to = None

        if name == u"territory":
            _territories_db[str(self._territoryId)] = territory_db_item(
                names = self._names,
                locales = self._locales,
                languages = self._languages,
                keyboards = self._keyboards,
                consolefonts = self._consolefonts,
                timezones = self._timezones)

            # clean after ourselves
            self._territoryId = None
            self._names = None
            self._locales = None
            self._languages = None
            self._keyboards = None
            self._consolefonts = None
            self._timezones = None

        # populating dictionaries
        elif name == u"name":
            self._names[str(self._item_id)] = self._item_name
            self._clear_item()
        elif name == u"locale":
            self._locales[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"language":
            self._languages[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"keyboard":
            self._keyboards[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"consolefont":
            self._consolefonts[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"timezone":
            self._timezones[str(self._item_id)] = int(self._item_rank)
            self._clear_item()

    def _clear_item(self):
        self._item_id = None
        self._item_name = None
        self._item_rank = None

class KeyboardsContentHandler(LangtableContentHandler):
    """Handler for SAX events produced when parsing the keyboards.xml file."""

    def __init__(self):
        super(KeyboardsContentHandler, self).__init__()

        # simple values
        self._keyboardId = None
        self._description = None
        self._ascii = None
        self._comment = None

        # helper variables
        self._item_id = None
        self._item_rank = None

        # dictionaries
        self._languages = None
        self._territories = None

    def startElement(self, name, attrs):
        if name == u"keyboard":
            self._languages = dict()
            self._territories = dict()

        # non-dict values
        elif name == u"keyboardId":
            self._save_to = "_keyboardId"
        elif name == u"description":
            self._save_to = "_description"
        elif name == u"ascii":
            self._save_to = "_ascii"
        elif name == u"comment":
            self._save_to = "_comment"

        # dict items
        elif name in (u"languageId", u"territoryId"):
            self._save_to = "_item_id"
        elif name == u"rank":
            self._save_to = "_item_rank"

    def endElement(self, name):
        # we don't allow text to appear on the same level as elements so outside
        # of an element no text should appear
        self._save_to = None

        if name == u"keyboard":
            _keyboards_db[str(self._keyboardId)] = keyboard_db_item(
                description = self._description,
                ascii = self._ascii == u"True",
                comment = self._comment,
                languages = self._languages,
                territories = self._territories)

            # clean after ourselves
            self._keyboardId = None
            self._description = None
            self._ascii = None
            self._comment = None
            self._languages = None
            self._territories = None

        # populating dictionaries
        elif name == u"language":
            self._languages[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"territory":
            self._territories[str(self._item_id)] = int(self._item_rank)
            self._clear_item()

    def _clear_item(self):
        self._item_id = None
        self._item_rank = None

class LanguagesContentHandler(LangtableContentHandler):
    """Handler for SAX events produced when parsing the languages.xml file."""

    def __init__(self):
        super(LanguagesContentHandler, self).__init__()
        # simple values
        self._languageId = None
        self._iso639_1 = None
        self._iso639_2_t = None
        self._iso639_2_b = None

        # helper variables
        self._item_id = None
        self._item_rank = None
        self._item_name = None

        # flag to distinguish 'languageId' elements inside and outside of the
        # 'names' element
        self._in_names = False

        # dictionaries
        self._names = None
        self._locales = None
        self._territories = None
        self._keyboards = None
        self._consolefonts = None
        self._timezones = None

    def startElement(self, name, attrs):
        if name == u"language":
            self._names = dict()
            self._locales = dict()
            self._territories = dict()
            self._keyboards = dict()
            self._consolefonts = dict()
            self._timezones = dict()

        # non-dict values
        elif name == u"languageId" and not self._in_names:
            # ID of the language
            self._save_to = "_languageId"
        elif name == u"iso639-1":
            self._save_to = "_iso639_1"
        elif name == u"iso639-2-t":
            self._save_to = "_iso639_2_t"
        elif name == u"iso639-2-b":
            self._save_to = "_iso639_2_b"
        elif name == u"names":
            self._in_names = True

        # dict items
        elif name in (u"localeId", u"territoryId", u"keyboardId",
                      u"consolefontId", u"timezoneId"):
            self._save_to = "_item_id"
        elif name == u"languageId" and self._in_names:
            # ID of the translated name's language
            self._save_to = "_item_id"
        elif name == u"trName":
            self._save_to = "_item_name"
        elif name == u"rank":
            self._save_to = "_item_rank"

    def endElement(self, name):
        # we don't allow text to appear on the same level as elements so outside
        # of an element no text should appear
        self._save_to = None

        if name == u"language":
            _languages_db[str(self._languageId)] = language_db_item(
                iso639_1 = self._iso639_1,
                iso639_2_t = self._iso639_2_t,
                iso639_2_b = self._iso639_2_b,
                names = self._names,
                locales = self._locales,
                territories = self._territories,
                keyboards = self._keyboards,
                consolefonts = self._consolefonts,
                timezones = self._timezones)

            # clean after ourselves
            self._languageId = None
            self._names = None
            self._locales = None
            self._territories = None
            self._keyboards = None
            self._consolefonts = None
            self._timezones = None

        # leaving the "names" element
        elif name == u"names":
            self._in_names = False

        # populating dictionaries
        elif name == u"name":
            self._names[str(self._item_id)] = self._item_name
            self._clear_item()
        elif name == u"locale":
            self._locales[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"territory":
            self._territories[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"keyboard":
            self._keyboards[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"consolefont":
            self._consolefonts[str(self._item_id)] = int(self._item_rank)
            self._clear_item()
        elif name == u"timezone":
            self._timezones[str(self._item_id)] = int(self._item_rank)
            self._clear_item()

    def _clear_item(self):
        self._item_id = None
        self._item_name = None
        self._item_rank = None

def _write_territories_file(file):
    '''
    Only for internal use
    '''
    file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write('<territories>\n')
    for territoryId in sorted(_territories_db):
        file.write('  <territory>\n')
        file.write('    <territoryId>'+territoryId+'</territoryId>\n')
        names = _territories_db[territoryId].names
        file.write('    <names>\n')
        for name in sorted(names):
            file.write(
                '      <name>'
                +'<languageId>'+name+'</languageId>'
                +'<name>'+names[name].encode('UTF-8')+'</name>'
                +'</name>\n')
        file.write('    </names>\n')
        locales = _territories_db[territoryId].locales
        file.write('    <locales>\n')
        for localeId, rank in sorted(locales.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <locale>'
                +'<localeId>'+localeId+'</localeId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</locale>\n')
        file.write('    </locales>\n')
        languages = _territories_db[territoryId].languages
        file.write('    <languages>\n')
        for languageId, rank in sorted(languages.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <language>'
                +'<languageId>'+languageId+'</languageId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</language>\n')
        file.write('    </languages>\n')
        keyboards = _territories_db[territoryId].keyboards
        file.write('    <keyboards>\n')
        for keyboardId, rank in sorted(keyboards.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <keyboard>'
                +'<keyboardId>'+keyboardId+'</keyboardId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</keyboard>\n')
        file.write('    </keyboards>\n')
        consolefonts = _territories_db[territoryId].consolefonts
        file.write('    <consolefonts>\n')
        for consolefontId, rank in sorted(consolefonts.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <consolefont>'
                +'<consolefontId>'+consolefontId+'</consolefontId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</consolefont>\n')
        file.write('    </consolefonts>\n')
        timezones = _territories_db[territoryId].timezones
        file.write('    <timezones>\n')
        for timezoneId, rank in sorted(timezones.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <timezone>'
                +'<timezoneId>'+timezoneId+'</timezoneId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</timezone>\n')
        file.write('    </timezones>\n')
        file.write('  </territory>\n')
    file.write('</territories>\n')
    return

def _write_languages_file(file):
    '''
    Only for internal use
    '''
    file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write('<languages>\n')
    for languageId in sorted(_languages_db):
        file.write('  <language>\n')
        file.write('    <languageId>'+languageId+'</languageId>\n')
        file.write('    <iso639-1>'+str(_languages_db[languageId].iso639_1)+'</iso639-1>\n')
        file.write('    <iso639-2-t>'+str(_languages_db[languageId].iso639_2_t)+'</iso639-2-t>\n')
        file.write('    <iso639-2-b>'+str(_languages_db[languageId].iso639_2_b)+'</iso639-2-b>\n')
        names = _languages_db[languageId].names
        file.write('    <names>\n')
        for name in sorted(names):
            file.write(
                '      <name>'
                +'<languageId>'+name+'</languageId>'
                +'<name>'+names[name].encode('UTF-8')+'</name>'
                +'</name>\n')
        file.write('    </names>\n')
        locales = _languages_db[languageId].locales
        file.write('    <locales>\n')
        for localeId, rank in sorted(locales.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <locale>'
                +'<localeId>'+localeId+'</localeId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</locale>\n')
        file.write('    </locales>\n')
        territories = _languages_db[languageId].territories
        file.write('    <territories>\n')
        for territoryId, rank in sorted(territories.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <territory>'
                +'<territoryId>'+territoryId+'</territoryId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</territory>\n')
        file.write('    </territories>\n')
        keyboards = _languages_db[languageId].keyboards
        file.write('    <keyboards>\n')
        for keyboardId, rank in sorted(keyboards.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <keyboard>'
                +'<keyboardId>'+keyboardId+'</keyboardId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</keyboard>\n')
        file.write('    </keyboards>\n')
        consolefonts = _languages_db[languageId].consolefonts
        file.write('    <consolefonts>\n')
        for consolefontId, rank in sorted(consolefonts.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <consolefont>'
                +'<consolefontId>'+consolefontId+'</consolefontId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</consolefont>\n')
        file.write('    </consolefonts>\n')
        timezones = _languages_db[languageId].timezones
        file.write('    <timezones>\n')
        for timezoneId, rank in sorted(timezones.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <timezone>'
                +'<timezoneId>'+timezoneId+'</timezoneId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</timezone>\n')
        file.write('    </timezones>\n')
        file.write('  </language>\n')
    file.write('</languages>\n')
    return

def _write_keyboards_file(file):
    '''
    Only for internal use
    '''
    file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write('<keyboards>\n')
    for keyboardId in sorted(_keyboards_db):
        file.write('  <keyboard>\n')
        file.write('    <keyboardId>'+keyboardId+'</keyboardId>\n')
        file.write('    <description>'+_keyboards_db[keyboardId].description+'</description>\n')
        file.write('    <ascii>'+str(_keyboards_db[keyboardId].ascii)+'</ascii>\n')
        if _keyboards_db[keyboardId].comment != None:
            file.write('    <comment>'+_keyboards_db[keyboardId].comment.encode('UTF-8')+'</comment>\n')
        languages = _keyboards_db[keyboardId].languages
        file.write('    <languages>\n')
        for languageId, rank in sorted(languages.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <language>'
                +'<languageId>'+languageId+'</languageId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</language>\n')
        file.write('    </languages>\n')
        territories = _keyboards_db[keyboardId].territories
        file.write('    <territories>\n')
        for territoryId, rank in sorted(territories.items(), key=lambda x: (-1*x[1],x[0])):
            file.write(
                '      <territory>'
                +'<territoryId>'+territoryId+'</territoryId>'
                +'<rank>'+str(rank)+'</rank>'
                +'</territory>\n')
        file.write('    </territories>\n')
        file.write('  </keyboard>\n')
    file.write('</keyboards>\n')
    return

def _expat_parse(file, sax_handler):
    """
    Only for internal use. Parses a given file object with a given SAX handler
    using an expat parser.
    """

    parser = xml.parsers.expat.ParserCreate()
    parser.StartElementHandler = sax_handler.startElement
    parser.EndElementHandler = sax_handler.endElement
    parser.CharacterDataHandler = sax_handler.characters
    parser.ParseFile(file)

def _read_file(datadir, filename, sax_handler):
    '''
    Only for internal use
    '''

    for dir in [datadir, '.']:
        path = os.path.join(dir, filename)
        if os.path.isfile(path):
            with open(path) as file:
                logging.info('reading file=%s' %file)
                _expat_parse(file, sax_handler)
            return
        path = os.path.join(dir, filename+'.gz')
        if os.path.isfile(path):
            with gzip.open(path) as file:
                logging.info('reading file=%s' %file)
                _expat_parse(file, sax_handler)
            return
    logging.info('no readable file found.')

def _write_files(territoriesfilename, languagesfilename, keyboardsfilename):
    '''
    Only for internal use
    '''
    with open(territoriesfilename, 'w') as territoriesfile:
        logging.info("writing territories file=%s" %territoriesfile)
        _write_territories_file(territoriesfile)
    with open(languagesfilename, 'w') as languagesfile:
        logging.info("writing languages file=%s" %languagesfile)
        _write_languages_file(languagesfile)
    with open(keyboardsfilename, 'w') as keyboardsfile:
        logging.info("writing keyboards file=%s" %keyboardsfile)
        _write_keyboards_file(keyboardsfile)
    return

def _dictionary_to_ranked_list(dict, reverse=True):
    sorted_list = []
    for item in sorted(dict, key=dict.get, reverse=reverse):
        sorted_list.append([item, dict[item]])
    return sorted_list

def _ranked_list_to_list(list):
    return map(lambda x: x[0], list)

def _make_ranked_list_concise(ranked_list, cut_off_factor=1000):
    if not len(ranked_list) > 1:
        return ranked_list
    for i in range(0,len(ranked_list)-1):
        if ranked_list[i][1]/ranked_list[i+1][1] > cut_off_factor:
            ranked_list = ranked_list[0:i+1]
            break
    return ranked_list

def _parse_and_split_languageId(languageId=None, scriptId=None, territoryId=None):
    '''
    Parses languageId and if it contains a valid ICU locale id,
    returns the values for language, script, and territory found
    in languageId instead of the original values given.

    Before parsing, it replaces glibc names for scripts like “latin”
    with the iso-15924 script names like “Latn”, both in the
    languageId and the scriptId parameter. I.e.  language id like
    “sr_latin_RS” is accepted as well and treated the same as
    “sr_Latn_RS”.
    '''
    for key in _glibc_script_ids:
        if scriptId:
            scriptId = scriptId.replace(key, _glibc_script_ids[key])
        if languageId:
            languageId = languageId.replace(key, _glibc_script_ids[key])
    if (languageId):
        match = _cldr_locale_pattern.match(languageId)
        if match:
            languageId = match.group('language')
            if match.group('script'):
                scriptId = match.group('script')
            if match.group('territory'):
                territoryId = match.group('territory')
        else:
            logging.info("languageId contains invalid locale id=%s" %languageId)
    return (languageId, scriptId, territoryId)

def territory_name(territoryId = None, languageIdQuery = None, scriptIdQuery = None, territoryIdQuery = None):
    '''Query translations of territory names

    Examples:

    Switzerland is called “Schweiz” in German:

    >>> print territory_name(territoryId="CH", languageIdQuery="de").encode("UTF-8")
    Schweiz

    And it is called “Svizzera” in Italian:

    >>> print territory_name(territoryId="CH", languageIdQuery="it").encode("UTF-8")
    Svizzera
    '''
    languageIdQuery, scriptIdQuery, territoryIdQuery = _parse_and_split_languageId(
        languageId=languageIdQuery,
        scriptId=scriptIdQuery,
        territoryId=territoryIdQuery)
    if territoryId in _territories_db:
        if languageIdQuery and scriptIdQuery and territoryIdQuery:
            icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery+'_'+territoryIdQuery
            if icuLocaleIdQuery in _territories_db[territoryId].names:
                return _territories_db[territoryId].names[icuLocaleIdQuery]
        if languageIdQuery and scriptIdQuery:
            icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery
            if icuLocaleIdQuery in _territories_db[territoryId].names:
                return _territories_db[territoryId].names[icuLocaleIdQuery]
        if languageIdQuery and territoryIdQuery:
            icuLocaleIdQuery = languageIdQuery+'_'+territoryIdQuery
            if icuLocaleIdQuery in _territories_db[territoryId].names:
                return _territories_db[territoryId].names[icuLocaleIdQuery]
        if languageIdQuery:
            icuLocaleIdQuery = languageIdQuery
            if icuLocaleIdQuery in _territories_db[territoryId].names:
                return _territories_db[territoryId].names[icuLocaleIdQuery]
    return ''

def language_name(languageId = None, scriptId = None, territoryId = None, languageIdQuery = None, scriptIdQuery = None, territoryIdQuery = None):
    '''Query translations of language names

    Examples:

    >>> print language_name(languageId="sr").encode("UTF-8")
    Српски

    I.e. the endonym for “Serbian” in the default Cyrillic script is
    “Српски”.

    If the script “Cyrl” is supplied as well, the result does not change
    because it is already clear that this is Serbian in Cyrillic script.
    So there is no need to print “Српски (Ћирилица)” here:

    >>> print language_name(languageId="sr", scriptId="Cyrl").encode("UTF-8")
    Српски

    And in Latin script the endonym is:

    >>> print language_name(languageId="sr", scriptId="Latn").encode("UTF-8")
    Srpski

    Again there is no need to print “Srpski (Latinica)” here, “Srpski”
    alone is already clear enough.

    And “Serbian” translated to English is:

    >>> print language_name(languageId="sr", languageIdQuery="en").encode("UTF-8")
    Serbian

    If the language name for “Serbian with Cyrillic script” is
    queried in English, the English name for the script needs to be in
    the output to distinguish it from “Serbian with Latin script”:

    >>> print language_name(languageId="sr", scriptId="Cyrl", languageIdQuery="en").encode("UTF-8")
    Serbian (Cyrillic)

    >>> print language_name(languageId="sr", scriptId="Latn", languageIdQuery="en").encode("UTF-8")
    Serbian (Latin)

    '''
    languageId, scriptId, territoryId = _parse_and_split_languageId(
        languageId=languageId,
        scriptId=scriptId,
        territoryId=territoryId)
    languageIdQuery, scriptIdQuery, territoryIdQuery = _parse_and_split_languageId(
        languageId=languageIdQuery,
        scriptId=scriptIdQuery,
        territoryId=territoryIdQuery)
    if not languageIdQuery:
        # get the endonym
        languageIdQuery = languageId
        scriptIdQuery = scriptId
        territoryIdQuery = territoryId
    if languageId and scriptId and territoryId:
        icuLocaleId = languageId+'_'+scriptId+'_'+territoryId
        if icuLocaleId in _languages_db:
            if languageIdQuery and scriptIdQuery and territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery and scriptIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if  languageIdQuery and  territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery:
                icuLocaleIdQuery = languageIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
    if languageId and scriptId:
        icuLocaleId = languageId+'_'+scriptId
        if icuLocaleId in _languages_db:
            if languageIdQuery and  scriptIdQuery and territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery and  scriptIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if  languageIdQuery and  territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery:
                icuLocaleIdQuery = languageIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
    if languageId and territoryId:
        icuLocaleId = languageId+'_'+territoryId
        if icuLocaleId in _languages_db:
            if languageIdQuery and  scriptIdQuery and territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery and  scriptIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if  languageIdQuery and  territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery:
                icuLocaleIdQuery = languageIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
        lname = language_name(languageId=languageId,
                              languageIdQuery=languageIdQuery,
                              scriptIdQuery=scriptIdQuery,
                              territoryIdQuery=territoryIdQuery)
        cname = territory_name(territoryId=territoryId,
                             languageIdQuery=languageIdQuery,
                             scriptIdQuery=scriptIdQuery,
                             territoryIdQuery=territoryIdQuery)
        if lname and cname:
            return lname + ' ('+cname+')'
    if languageId:
        icuLocaleId = languageId
        if icuLocaleId in _languages_db:
            if languageIdQuery and  scriptIdQuery and territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery and  scriptIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+scriptIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if  languageIdQuery and  territoryIdQuery:
                icuLocaleIdQuery = languageIdQuery+'_'+territoryIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
            if languageIdQuery:
                icuLocaleIdQuery = languageIdQuery
                if icuLocaleIdQuery in _languages_db[icuLocaleId].names:
                    return _languages_db[icuLocaleId].names[icuLocaleIdQuery]
    return ''

extra_bonus = 1000000

def list_locales(concise=True, show_weights=False, languageId = None, scriptId = None, territoryId = None):
    '''List suitable glibc locales

    Examples:

    List the suitable locales for the language “German”:

    >>> list_locales(languageId="de")
    ['de_DE.UTF-8', 'de_AT.UTF-8', 'de_CH.UTF-8', 'de_BE.UTF-8', 'de_LU.UTF-8']

    So this returns a list of locales for German. These lists are
    sorted in order of decreasing likelyhood, i.e. the most common
    value comes first.

    One can also list the possible locales for the territory “Switzerland”:

    >>> list_locales(territoryId="CH")
    ['de_CH.UTF-8', 'fr_CH.UTF-8', 'it_CH.UTF-8', 'wae_CH.UTF-8']


    If one knows both, the language “German” and the territory
    “Switzerland”, the result is unique:

    >>> list_locales(languageId="de", territoryId="CH")
    ['de_CH.UTF-8']

    '''
    ranked_locales = {}
    skipTerritory = False
    languageId, scriptId, territoryId = _parse_and_split_languageId(
        languageId=languageId,
        scriptId=scriptId,
        territoryId=territoryId)
    if languageId and scriptId and territoryId and languageId+'_'+scriptId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+scriptId+'_'+territoryId
        skipTerritory = True
    elif languageId and scriptId and languageId+'_'+scriptId in _languages_db:
        languageId = languageId+'_'+scriptId
    elif languageId and territoryId and languageId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+territoryId
        skipTerritory = True
    language_bonus = 100
    if languageId in _languages_db:
        for locale in _languages_db[languageId].locales:
            if _languages_db[languageId].locales[locale] != 0:
                if locale not in ranked_locales:
                    ranked_locales[locale] = _languages_db[languageId].locales[locale]
                else:
                    ranked_locales[locale] *= _languages_db[languageId].locales[locale]
                    ranked_locales[locale] *= extra_bonus
                ranked_locales[locale] *= language_bonus
    territory_bonus = 1
    if territoryId in _territories_db and not skipTerritory:
        for locale in _territories_db[territoryId].locales:
            if _territories_db[territoryId].locales[locale] != 0:
                if locale not in ranked_locales:
                    ranked_locales[locale] = _territories_db[territoryId].locales[locale]
                else:
                    ranked_locales[locale] *= _territories_db[territoryId].locales[locale]
                    ranked_locales[locale] *= extra_bonus
                ranked_locales[locale] *= territory_bonus
    ranked_list = _dictionary_to_ranked_list(ranked_locales)
    if concise:
        ranked_list = _make_ranked_list_concise(ranked_list)
    if show_weights:
        return ranked_list
    else:
        return _ranked_list_to_list(ranked_list)

def list_keyboards(concise=True, show_weights=False, languageId = None, scriptId = None, territoryId = None):
    '''List likely X11 keyboard layouts

    Examples:

    Listing likely X11 keyboard layouts for “German”:

    >>> list_keyboards(languageId="de")
    ['de(nodeadkeys)', 'de(deadacute)', 'at(nodeadkeys)', 'ch', 'be(oss)']

    Listing likely X11 keyboard layouts for “Switzerland”:

    >>> list_keyboards(territoryId="CH")
    ['ch', 'ch(fr)', 'it']

    When specifying both “German” *and* “Switzerland”, the
    returned X11 keyboard layout is unique:

    >>> list_keyboards(languageId="de", territoryId="CH")
    ['ch']
    '''
    ranked_keyboards = {}
    skipTerritory = False
    languageId, scriptId, territoryId = _parse_and_split_languageId(
        languageId=languageId,
        scriptId=scriptId,
        territoryId=territoryId)
    if languageId and scriptId and territoryId and languageId+'_'+scriptId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+scriptId+'_'+territoryId
        skipTerritory = True
    elif languageId and scriptId and languageId+'_'+scriptId in _languages_db:
        languageId = languageId+'_'+scriptId
    elif languageId and territoryId and languageId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+territoryId
        skipTerritory = True
    language_bonus = 1
    if languageId in _languages_db:
        for keyboard in _languages_db[languageId].keyboards:
            if _languages_db[languageId].keyboards[keyboard] != 0:
                if keyboard not in ranked_keyboards:
                    ranked_keyboards[keyboard] = _languages_db[languageId].keyboards[keyboard]
                else:
                    ranked_keyboards[keyboard] *= _languages_db[languageId].keyboards[keyboard]
                    ranked_keyboards[keyboard] *= extra_bonus
                ranked_keyboards[keyboard] *= language_bonus
    territory_bonus = 1
    if territoryId in _territories_db:
        for keyboard in _territories_db[territoryId].keyboards:
            if _territories_db[territoryId].keyboards[keyboard] != 0:
                if keyboard not in ranked_keyboards:
                    ranked_keyboards[keyboard] = _territories_db[territoryId].keyboards[keyboard]
                else:
                    ranked_keyboards[keyboard] *= _territories_db[territoryId].keyboards[keyboard]
                    ranked_keyboards[keyboard] *= extra_bonus
                ranked_keyboards[keyboard] *= territory_bonus
    ranked_list = _dictionary_to_ranked_list(ranked_keyboards)
    if concise:
        ranked_list = _make_ranked_list_concise(ranked_list)
    if show_weights:
        return ranked_list
    else:
        return _ranked_list_to_list(ranked_list)

def list_consolefonts(concise=True, show_weights=False, languageId = None, scriptId = None, territoryId = None):
    ranked_consolefonts = {}
    skipTerritory = False
    languageId, scriptId, territoryId = _parse_and_split_languageId(
        languageId=languageId,
        scriptId=scriptId,
        territoryId=territoryId)
    if languageId and scriptId and territoryId and languageId+'_'+scriptId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+scriptId+'_'+territoryId
        skipTerritory = True
    elif languageId and scriptId and languageId+'_'+scriptId in _languages_db:
        languageId = languageId+'_'+scriptId
    elif languageId and territoryId and languageId+'_'+territoryId in _languages_db:
        languageId = languageId+'_'+territoryId
        skipTerritory = True
    language_bonus = 100
    if languageId in _languages_db:
        for consolefont in _languages_db[languageId].consolefonts:
            if _languages_db[languageId].consolefonts[consolefont] != 0:
                if consolefont not in ranked_consolefonts:
                    ranked_consolefonts[consolefont] = _languages_db[languageId].consolefonts[consolefont]
                else:
                    ranked_consolefonts[consolefont] *= _languages_db[languageId].consolefonts[consolefont]
                    ranked_consolefonts[consolefont] *= extra_bonus
                ranked_consolefonts[consolefont] *= language_bonus
    territory_bonus = 1
    if territoryId in _territories_db:
        for consolefont in _territories_db[territoryId].consolefonts:
            if _territories_db[territoryId].consolefonts[consolefont] != 0:
                if consolefont not in ranked_consolefonts:
                    ranked_consolefonts[consolefont] = _territories_db[territoryId].consolefonts[consolefont]
                else:
                    ranked_consolefonts[consolefont] *= _territories_db[territoryId].consolefonts[consolefont]
                    ranked_consolefonts[consolefont] *= extra_bonus
                ranked_consolefonts[consolefont] *= territory_bonus
    ranked_list = _dictionary_to_ranked_list(ranked_consolefonts)
    if concise:
        ranked_list = _make_ranked_list_concise(ranked_list)
    if show_weights:
        return ranked_list
    else:
        return _ranked_list_to_list(ranked_list)

def supports_ascii(keyboardId=None):
    '''
    Returns True if the keyboard layout with that id can be used to
    type ASCII, returns false if the keyboard layout can not be used
    to type ASCII or if typing ASCII with that keyboard layout is
    difficult.

    >>> supports_ascii("jp")
    True
    >>> supports_ascii("ru")
    False
    '''
    if keyboardId in _keyboards_db:
        return _keyboards_db[keyboardId].ascii
    return False

def _test_cldr_locale_pattern(localeId):
    '''
    Internal test function, do not use this.
    '''
    match = _cldr_locale_pattern.match(localeId)
    if match:
        return [('language', match.group('language')), ('script', match.group('script')), ('territory', match.group('territory'))]
    else:
        return  []

def _test_language_territory(show_weights=False, languageId=None, scriptId=None, territoryId=None):
    '''
    Internal test function, do not use this.
    '''
    print(str(languageId)+": "
          +repr(list_locales(show_weights=show_weights,languageId=languageId))
          +'\n'
          +str(territoryId)+": "
          +repr(list_locales(show_weights=show_weights,territoryId=territoryId))
          +'\n'
          +" +: "
          +repr(list_locales(show_weights=show_weights,languageId=languageId,scriptId=scriptId,territoryId=territoryId))
          +'\n'
          +str(languageId)+": "
          +repr(list_keyboards(show_weights=show_weights,languageId=languageId))
          +'\n'
          +str(territoryId)+": "
          +repr(list_keyboards(show_weights=show_weights,territoryId=territoryId))
          +'\n'
          +" +: "
          +repr(list_keyboards(show_weights=show_weights,languageId=languageId,scriptId=scriptId,territoryId=territoryId))
          )
    return

def _init(debug = False,
         logfilename = '/dev/null',
         datadir = _datadir):

    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    logging.basicConfig(filename=logfilename,
                        filemode="w",
                        format="%(levelname)s: %(message)s",
                        level=log_level)

    _read_file(datadir, 'territories.xml', TerritoriesContentHandler())
    _read_file(datadir, 'languages.xml', LanguagesContentHandler())
    _read_file(datadir, 'keyboards.xml', KeyboardsContentHandler())

class __ModuleInitializer:
    def __init__(self):
        _init()
        return

    def __del__(self):
        return

__module_init = __ModuleInitializer()

if __name__ == "__main__":
    import doctest
    _init()
    doctest.testmod()