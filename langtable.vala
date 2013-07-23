using Gee;

namespace langtable {
	private class StringRankMap : HashMap<string, uint32> {
	}

	private class NamesMap : HashMap<string, string> {
	}

	private class KeyboardsDB : HashMap<string, KeyboardsDBitem> {
	}

	private class TerritoriesDB: HashMap<string, TerritoriesDBitem> {
	}

	private class LanguagesDB: HashMap<string, LanguagesDBitem> {
	}

	// cannot create instances here, use pointers instead
	private KeyboardsDB* keyboards_db_ptr;
	private TerritoriesDB* territories_db_ptr;
	private LanguagesDB* languages_db_ptr;

	/***************** keyboards.xml parsing *****************/
	private enum KeyboardFields {
		// attributes of the KeyboardsDBitem
		keyboardId,
		description,
		comment,

		// a helper field for storing temp values (e.g. bool/int strings)
		tmp_field,

		// fields for storing item IDs and ranks
		item_id,
		item_rank,
		NONE,
	}

	private class KeyboardsDBitem : GLib.Object {
		public string keyboardId;
		public string description;
		public string comment;
		public bool ascii;
		public StringRankMap languages;
		public StringRankMap territories;

		public KeyboardsDBitem () {
			keyboardId = "";
			description = "";
			comment = "";
			languages = new StringRankMap ();
			territories = new StringRankMap ();
		}
	}

	private class KeyboardParsingDriver : GLib.Object {
		public KeyboardFields store_to;
		public KeyboardsDBitem curr_item;
		public string item_id;
		public string item_rank;
		public string tmp_field;

		public KeyboardParsingDriver () {
			store_to = KeyboardFields.NONE;
			curr_item = null;
			item_id = "";
			item_rank = "";
			tmp_field = "";
		}
	}

	private void keyboardStartElement (void* data, string name, string[] attrs) {
		KeyboardParsingDriver driver = data as KeyboardParsingDriver;

		switch (name) {
		case "keyboard":
			driver.curr_item = new KeyboardsDBitem ();
			break;
		case "keyboardId":
			driver.store_to = KeyboardFields.keyboardId;
			break;
		case "description":
			driver.store_to = KeyboardFields.description;
			break;
		case "ascii":
			driver.store_to = KeyboardFields.tmp_field;
			break;
		case "comment":
			driver.store_to = KeyboardFields.comment;
			break;
		case "languageId":
		case "territoryId":
			driver.store_to = KeyboardFields.item_id;
		    break;
		case "rank":
			driver.store_to = KeyboardFields.item_rank;
			break;
		}
	}

	private void keyboardEndElement (void* data, string name) {
		KeyboardParsingDriver driver = data as KeyboardParsingDriver;
		HashMap<string, KeyboardsDBitem> keyboards_db = keyboards_db_ptr;

		switch (name) {
		case "ascii":
			driver.curr_item.ascii = driver.tmp_field == "True";
			driver.tmp_field = "";
			break;
		case "keyboard":
			keyboards_db[driver.curr_item.keyboardId] = driver.curr_item;
			driver.curr_item = null;
			break;
		case "language":
			driver.curr_item.languages[driver.item_id] = int.parse(driver.item_rank);
			driver.item_id = "";
			break;
		case "territory":
			driver.curr_item.territories[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		}

		driver.store_to = KeyboardFields.NONE;
	}

	private void keyboardCharacters (void* data, string char_buf, int len)	{
		KeyboardParsingDriver driver = data as KeyboardParsingDriver;
		string chars = char_buf[0:len].strip ();

		if (chars == "")
			// nothing to save
			return;

		if (driver.curr_item == null || driver.store_to == KeyboardFields.NONE)
			// no idea where to save characters
			return;

		switch (driver.store_to) {
		case KeyboardFields.keyboardId:
			driver.curr_item.keyboardId += chars;
			break;
		case KeyboardFields.description:
			driver.curr_item.description += chars;
			break;
		case KeyboardFields.comment:
			driver.curr_item.comment += chars;
			break;
		case KeyboardFields.tmp_field:
			driver.tmp_field += chars;
			break;
		case KeyboardFields.item_id:
			driver.item_id += chars;
			break;
		case KeyboardFields.item_rank:
			driver.item_rank += chars;
			break;
		}
	}

	/***************** territories.xml parsing *****************/
	private enum TerritoryFields {
		// attributes of the TerritoriesDBitem
		territoryId,

		// fields for storing item IDs, ranks and translated names
		item_id,
		item_rank,
		item_name,
		NONE,
	}

	private class TerritoriesDBitem : GLib.Object {
		public string territoryId;

		public NamesMap names;
		public StringRankMap languages;
		public StringRankMap locales;
		public StringRankMap keyboards;
		public StringRankMap consolefonts;
		public StringRankMap timezones;

		public TerritoriesDBitem () {
			territoryId = "";
			names = new NamesMap ();
			languages = new StringRankMap ();
			locales = new StringRankMap ();
			keyboards = new StringRankMap ();
			consolefonts = new StringRankMap ();
			timezones = new StringRankMap ();
		}
	}

	private class TerritoryParsingDriver : GLib.Object {
		public TerritoryFields store_to;
		public TerritoriesDBitem curr_item;
		public string item_id;
		public string item_rank;
		public string item_name;

		public TerritoryParsingDriver () {
			store_to = TerritoryFields.NONE;
			curr_item = null;
			item_id = "";
			item_rank = "";
			item_name = "";
		}
	}

	private void territoryStartElement (void* data, string name, string[] attrs) {
		TerritoryParsingDriver driver = data as TerritoryParsingDriver;

		switch (name) {
		case "territory":
			driver.curr_item = new TerritoriesDBitem ();
			break;
		case "territoryId":
			driver.store_to = TerritoryFields.territoryId;
			break;
		case "languageId":
		case "localeId":
		case "keyboardId":
		case "consolefontId":
		case "timezoneId":
			driver.store_to = TerritoryFields.item_id;
		    break;
		case "trName":
			driver.store_to = TerritoryFields.item_name;
			break;
		case "rank":
			driver.store_to = TerritoryFields.item_rank;
			break;
		}
	}

	private void territoryEndElement (void* data, string name) {
		TerritoryParsingDriver driver = data as TerritoryParsingDriver;
		HashMap<string, TerritoriesDBitem> territories_db = territories_db_ptr;

		switch (name) {
		case "territory":
			territories_db[driver.curr_item.territoryId] = driver.curr_item;
			driver.curr_item = null;
			break;
		case "name":
			driver.curr_item.names[driver.item_id] = driver.item_name;
			driver.item_id = "";
			driver.item_name = "";
			break;
		case "language":
			driver.curr_item.languages[driver.item_id] = int.parse(driver.item_rank);
			driver.item_id = "";
			break;
		case "locale":
			driver.curr_item.locales[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "keyboard":
			driver.curr_item.keyboards[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "consolefont":
			driver.curr_item.consolefonts[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "timezone":
			driver.curr_item.timezones[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		}

		driver.store_to = TerritoryFields.NONE;
	}

	private void territoryCharacters (void* data, string char_buf, int len)	{
		TerritoryParsingDriver driver = data as TerritoryParsingDriver;
		string chars = char_buf[0:len].strip ();

		if (chars == "")
			// nothing to save
			return;

		if (driver.curr_item == null || driver.store_to == TerritoryFields.NONE)
			// no idea where to save characters
			return;

		switch (driver.store_to) {
		case TerritoryFields.territoryId:
			driver.curr_item.territoryId += chars;
			break;
		case TerritoryFields.item_id:
			driver.item_id += chars;
			break;
		case TerritoryFields.item_rank:
			driver.item_rank += chars;
			break;
		case TerritoryFields.item_name:
			driver.item_name += chars;
			break;
		}
	}

	/***************** languages.xml parsing *****************/
	private enum LanguageFields {
		// attributes of the LanguagesDBitem
		languageId,
		iso639_1,
		iso639_2_t,
		iso639_2_b,

		// fields for storing item IDs, ranks and translated names
		item_id,
		item_rank,
		item_name,
		NONE,
	}

	private class LanguagesDBitem : GLib.Object {
		public string languageId;
		public string iso639_1;
		public string iso639_2_t;
		public string iso639_2_b;

		public NamesMap names;
		public StringRankMap locales;
		public StringRankMap territories;
		public StringRankMap keyboards;
		public StringRankMap consolefonts;
		public StringRankMap timezones;

		public LanguagesDBitem () {
			languageId = "";
			iso639_1 = "";
			iso639_2_t = "";
			iso639_2_b = "";
			names = new NamesMap ();
			locales = new StringRankMap ();
			territories = new StringRankMap ();
			keyboards = new StringRankMap ();
			consolefonts = new StringRankMap ();
			timezones = new StringRankMap ();
		}
	}

	private class LanguageParsingDriver : GLib.Object {
		public LanguageFields store_to;
		public LanguagesDBitem curr_item;
		public string item_id;
		public string item_rank;
		public string item_name;
		public bool in_names;

		public LanguageParsingDriver () {
			store_to = LanguageFields.NONE;
			curr_item = null;
			item_id = "";
			item_rank = "";
			item_name = "";
			in_names = false;
		}
	}

	private void languageStartElement (void* data, string name, string[] attrs) {
		LanguageParsingDriver driver = data as LanguageParsingDriver;

		switch (name) {
		case "language":
			driver.curr_item = new LanguagesDBitem ();
			break;
		case "languageId":
			if (!driver.in_names)
				driver.store_to = LanguageFields.languageId;
			else
				driver.store_to = LanguageFields.item_id;
			break;
		case "iso639-1":
			driver.store_to = LanguageFields.iso639_1;
			break;
		case "iso639-2-t":
			driver.store_to = LanguageFields.iso639_2_t;
			break;
		case "iso639-2-b":
			driver.store_to = LanguageFields.iso639_2_b;
			break;
		case "names":
			driver.in_names = true;
			break;
		case "localeId":
		case "keyboardId":
		case "territoryId":
		case "consolefontId":
		case "timezoneId":
			driver.store_to = LanguageFields.item_id;
		    break;
		case "trName":
			driver.store_to = LanguageFields.item_name;
			break;
		case "rank":
			driver.store_to = LanguageFields.item_rank;
			break;
		}
	}

	private void languageEndElement (void* data, string name) {
		LanguageParsingDriver driver = data as LanguageParsingDriver;
		HashMap<string, LanguagesDBitem> languages_db = languages_db_ptr;

		switch (name) {
		case "language":
			languages_db[driver.curr_item.languageId] = driver.curr_item;
			driver.curr_item = null;
			break;
		case "names":
			driver.in_names = false;
			break;
		case "name":
			driver.curr_item.names[driver.item_id] = driver.item_name;
			driver.item_id = "";
			driver.item_name = "";
			break;
		case "locale":
			driver.curr_item.locales[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "keyboard":
			driver.curr_item.keyboards[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "territory":
			driver.curr_item.territories[driver.item_id] = int.parse(driver.item_rank);
			driver.item_id = "";
			break;
		case "consolefont":
			driver.curr_item.consolefonts[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		case "timezone":
			driver.curr_item.timezones[driver.item_id] = int.parse(driver.item_rank);
			driver.item_rank = "";
			break;
		}

		driver.store_to = LanguageFields.NONE;
	}

	private void languageCharacters (void* data, string char_buf, int len)	{
		LanguageParsingDriver driver = data as LanguageParsingDriver;
		string chars = char_buf[0:len].strip ();

		if (chars == "")
			// nothing to save
			return;

		if (driver.curr_item == null || driver.store_to == LanguageFields.NONE)
			// no idea where to save characters
			return;

		switch (driver.store_to) {
		case LanguageFields.languageId:
			driver.curr_item.languageId += chars;
			break;
		case LanguageFields.iso639_1:
			driver.curr_item.iso639_1 += chars;
			break;
		case LanguageFields.iso639_2_t:
			driver.curr_item.iso639_2_t += chars;
			break;
		case LanguageFields.iso639_2_b:
			driver.curr_item.iso639_2_b += chars;
			break;
		case LanguageFields.item_id:
			driver.item_id += chars;
			break;
		case LanguageFields.item_rank:
			driver.item_rank += chars;
			break;
		case LanguageFields.item_name:
			driver.item_name += chars;
			break;
		}
	}

	private void parse_file (Xml.SAXHandler handler, void* driver, string fpath) {
		string real_path = fpath;

		if (!FileUtils.test (real_path, FileTest.EXISTS)) {
			if (FileUtils.test (real_path + ".gz", FileTest.EXISTS))
				real_path += ".gz";
			else
				// raise exception instead or return bool?
				return;
		}

		handler.user_parse_file (driver, real_path);
	}

	public int main (string[] args) {
		keyboards_db_ptr = new KeyboardsDB ();
		territories_db_ptr = new TerritoriesDB ();
		languages_db_ptr = new LanguagesDB ();

		var handler = Xml.SAXHandler ();

		var kb_driver = new KeyboardParsingDriver ();
		var ter_driver = new TerritoryParsingDriver ();
		var lang_driver = new LanguageParsingDriver ();

		handler.startElement = keyboardStartElement;
		handler.endElement = keyboardEndElement;
		handler.characters = keyboardCharacters;

		parse_file (handler, kb_driver, "/usr/share/langtable/keyboards.xml");

		handler = Xml.SAXHandler ();
		handler.startElement = territoryStartElement;
		handler.endElement = territoryEndElement;
		handler.characters = territoryCharacters;

		parse_file (handler, ter_driver, "/usr/share/langtable/territories.xml");

		handler = Xml.SAXHandler ();
		handler.startElement = languageStartElement;
		handler.endElement = languageEndElement;
		handler.characters = languageCharacters;

		parse_file (handler, lang_driver, "/usr/share/langtable/languages.xml");

		KeyboardsDB keyboards_db = keyboards_db_ptr;
		TerritoriesDB territories_db = territories_db_ptr;
		LanguagesDB languages_db = languages_db_ptr;

		foreach (var entry in keyboards_db.entries) {
			stdout.printf ("Have keyboard '%s': '%s'\n", entry.key, entry.value.description);
		}

		foreach (var entry in territories_db.entries) {
			stdout.printf ("Have territory '%s'\n", entry.key);
		}

		foreach (var entry in languages_db.entries) {
			stdout.printf ("Have language '%s': '%s'\n", entry.key, entry.value.names["en"]);
		}

		return 0;
	}
}